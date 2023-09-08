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


def get_test_policy_id(endpoint, headers, account_id, logger):
    search_template = Template("""
    {
      actor {
        account(id: $account_id) {
          alerts {
            policiesSearch(searchCriteria: {name: "2W-CPU-Mem-100"}) {
              policies {
                name
                id
              }
            }
          }
        }
      }
    }
    """)
    search_template_fmtd = search_template.substitute({"account_id": account_id})
    nr_response = requests.post(endpoint,
                                headers=headers,
                                json={'query': search_template_fmtd}).json()
    try:
        policy_id = nr_response['data']['actor']['account']['alerts']['policiesSearch']['policies'][0]['id']
        logger.info(f'Utilization alert policy found: {policy_id}\n')
        return policy_id
    except [KeyError, IndexError] as e:
        logger.info(e)
        logger.info(nr_response)
        return 1


# create conditions for CPU and memory, associated with policy ID
def create_conditions(endpoint, headers, account_id, client_name, policy_id, logger):
    condition_template = Template("""
    mutation {
      alertsNrqlConditionStaticCreate(
        accountId: $account_id
        policyId: $policy_id
        condition: {
          enabled: true
          name: "$name"
          description: "$client_name $priority alert for $metric utilization."
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
              operator: ABOVE_OR_EQUALS
              threshold: $threshold
              priority: CRITICAL
              thresholdDuration: $duration
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

    # "CRITICAL": {
    #     "threshold": 99.9,
    #     "duration": 300
    # },

    conditions = {
        "CPU": {
            "name": "CPU_Utilization",
            "priority": {
                "MAJOR": {
                    "threshold": 95,
                    "duration": 600
                },
                "MINOR": {
                    "threshold": 90,
                    "duration": 900
                }
            },
            "nrql": "SELECT max(cpuPercent) from SystemSample facet hostname, provider.ec2InstanceId, tags.Name, "
                    "entityGuid, entityId"
        },
        "memory": {
            "name": "Memory_Utilization",
            "priority": {
                "MAJOR": {
                    "threshold": 95,
                    "duration": 600
                },
                "MINOR": {
                    "threshold": 90,
                    "duration": 900
                }
            },
            "nrql": "SELECT max(memoryUsedPercent) from SystemSample facet hostname, provider.ec2InstanceId, "
                    "tags.Name, "
                    "entityGuid, entityId"
        }
    }

    for c_key, condition in conditions.items():
        for p_key, priority in condition['priority'].items():
            logger.info(f'Creating {c_key} condition...')
            name = f"{p_key}_{condition['name']}_{str(priority['threshold'])}"

            condition_template_fmtd = condition_template.substitute({"account_id": account_id,
                                                                     "metric": c_key,
                                                                     "name": name,
                                                                     "nrql": condition["nrql"],
                                                                     "policy_id": policy_id,
                                                                     "client_name": client_name,
                                                                     "priority": p_key,
                                                                     "threshold": priority["threshold"],
                                                                     "duration": priority["duration"]})

            nr_response = requests.post(endpoint,
                                        headers=headers,
                                        json={'query': condition_template_fmtd}).json()

            try:
                condition_id = nr_response['data']['alertsNrqlConditionStaticCreate']['id']
                logger.info(f'   Condition {condition_id} {name} successfully created for policy {policy_id}.')
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
