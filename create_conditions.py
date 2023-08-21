from string import Template
import requests
import json


# create policy; return policy ID
def create_policy(endpoint, headers, account_id, logger):
    logger.info('Creating 2W-CPU-Mem-100 alert policy...')
    policy_template = Template("""
    mutation PolicyCreate {
      alertsPolicyCreate(
        accountId: $account_id
        policy: {name: "2W-CPU-Mem-100", incidentPreference: PER_CONDITION_AND_TARGET}
      ) {
        id
      }
    }
    """)

    policy_template_fmtd = policy_template.substitute({"account_id": account_id})
    nr_response = requests.post(endpoint,
                                headers=headers,
                                json={'query': policy_template_fmtd}).json()

    try:
        policy_id = nr_response['data']['alertsPolicyCreate']['id']
        logger.info(f'   Utilization alert policy successfully created: {policy_id}.')
        return policy_id
    except KeyError as e:
        logger.info(e)
        logger.info(nr_response)
        return 1


# create conditions for CPU and memory, associated with policy ID
def create_conditions(endpoint, headers, account_id, policy_id, logger):
    condition_template = Template("""
    mutation {
      alertsNrqlConditionStaticCreate(
        accountId: $account_id
        policyId: $policy_id
        condition: {
          enabled: true
          name: "$name"
          description: "Alert when $metric utilization is 100% for 5 minutes."
          nrql: {
            query:  "$nrql"
          }
          signal: {
            aggregationWindow: 60
            aggregationDelay: 120
            aggregationMethod: EVENT_FLOW
          }
          terms: [
            {
              operator: EQUALS
              threshold: 100
              priority: CRITICAL
              thresholdDuration: 300
              thresholdOccurrences: ALL
            }
          ]
          violationTimeLimitSeconds: 86400
        }
      ) {
        id
      }
    }
    """)

    # TODO: rename from URGENT to CRITICAL (P1) or MAJOR (P2) depending on desired ticket priority in FS
    conditions = {
        "CPU": {
            "name": "URGENT_CPU_Utilization_100",
            "nrql": "SELECT max(aws.ec2.CPUUtilization) from Metric where metricName = 'aws.ec2.CPUUtilization' facet "
                    "aws.ec2.InstanceId, tags.Name, entityGuid, entityId"
        },
        "memory": {
            "name": "URGENT_Memory_Utilization_100",
            "nrql": "SELECT max(host.memoryUsedPercent) from Metric where metricName = 'host.memoryUsedPercent' facet "
                    "aws.ec2.InstanceId, tags.Name, entityGuid, entityId"
        }
    }

    for key, condition in conditions.items():
        logger.info(f'Creating {key} condition...')

        condition_template_fmtd = condition_template.substitute({"account_id": account_id,
                                                                 "metric": key,
                                                                 "name": condition["name"],
                                                                 "nrql": condition["nrql"],
                                                                 "policy_id": policy_id})

        nr_response = requests.post(endpoint,
                                    headers=headers,
                                    json={'query': condition_template_fmtd}).json()

        try:
            condition_id = nr_response['data']['alertsNrqlConditionStaticCreate']['id']
            logger.info(f'   Condition {condition_id} {condition["name"]} successfully created for policy {policy_id}.')
        except (KeyError, TypeError) as e:
            logger.info(e)
            logger.info(nr_response)


# get Platform workflow; return workflow ID, issuesFilter ID, list of existing associated policies
def get_platform_workflow(endpoint, headers, account_id, logger):
    logger.info('Locating Platform workflow...')
    workflows_query = Template("""
        {
          actor {
            account(id: $account_id) {
              aiWorkflows {
                workflows {
                  entities {
                    id
                    name
                    issuesFilter {
                      id
                      predicates {
                        attribute
                        operator
                        values
                      }
                    }
                  }
                }
              }
            }
          }
        }
        """)

    workflows_query_fmtd = workflows_query.substitute({'account_id': account_id})
    nr_response = requests.post(endpoint,
                                headers=headers,
                                json={'query': workflows_query_fmtd}).json()

    for workflow in nr_response['data']['actor']['account']['aiWorkflows']['workflows']['entities']:
        if 'Platform' in workflow['name']:
            try:
                workflow_id = workflow["id"]
                filter_id = workflow['issuesFilter']['id']
                values_list = []
                for predicate in workflow['issuesFilter']['predicates']:
                    if predicate['attribute'] == 'labels.policyIds':
                        values_list = predicate['values']
                logger.info(f'   Platform workflow found: {workflow_id}\n'
                            f'      Filter ID: {filter_id}\n'
                            f'      Associated policies: {values_list}')

                return workflow_id, filter_id, values_list
            except KeyError as e:
                logger.info(e)
                logger.info(nr_response)
        else:
            continue


# update Platform workflow with updated list of policies
def update_workflow(endpoint, headers, account_id, policy_id, workflow_id, filter_id, values_list, logger):
    logger.info('Assigning alert policy to Platform workflow...')
    values_list = json.dumps(values_list)

    update_template = Template("""
    mutation UpdateWorkflow {
      aiWorkflowsUpdateWorkflow(
        accountId: $account_id
        updateWorkflowData: {
          id: "$workflow_id", 
          issuesFilter: {
            id: "$filter_id", 
            filterInput: {
              predicates: [
                {
                  values: $values_list, 
                  attribute: "labels.policyIds", 
                  operator: EXACTLY_MATCHES
                },
                {
                  attribute: "priority",
                  operator: EQUAL,
                  values: [
                    "CRITICAL"
                  ]
                }
              ] 
              type: FILTER
            }
          }
        }
      ) {
        workflow {
          id
          issuesFilter {
            predicates {
              attribute
              values
            }
          }
        }
        errors {
          type
          description
        }
      }
    }
    """)

    update_template_fmtd = update_template.substitute({'account_id': account_id,
                                                       'workflow_id': workflow_id,
                                                       'filter_id': filter_id,
                                                       'values_list': values_list})
    nr_response = requests.post(endpoint,
                                headers=headers,
                                json={'query': update_template_fmtd}).json()

    try:
        for predicate in nr_response['data']['aiWorkflowsUpdateWorkflow']['workflow']['issuesFilter']['predicates']:
            if predicate['attribute'] == 'labels.policyIds':
                values = predicate['values']
                if str(policy_id) in values:
                    logger.info('   Alert policy successfully added to Platform workflow.')
    except KeyError as e:
        logger.info(f'   Error: {e}')
