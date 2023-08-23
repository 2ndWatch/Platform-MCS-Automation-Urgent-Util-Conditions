from string import Template
import json
import requests


def create_muting_rules(endpoint, headers, account_id, logger):
    rules_dict = {
        "CPU": {
            "Alert 1": {
                "condition1": {
                    "attribute": "nrqlQuery",
                    "operator": "CONTAINS",
                    "values": "ec2.CPUUtilization"
                },
                "condition2": {
                    "attribute": "policyName",
                    "operator": "NOT_CONTAINS",
                    "values": "CPU-Mem"
                }
            },
            "Alert 2": {
                "condition1": {
                    "attribute": "policyName",
                    "operator": "CONTAINS",
                    "values": "Standard_Server"
                },
                "condition2": {
                    "attribute": "conditionName",
                    "operator": "CONTAINS",
                    "values": "CPU"
                }
            },
            "Alert 3": {
                "condition1": {
                    "attribute": "nrqlQuery",
                    "operator": "CONTAINS",
                    "values": "cpuPercent"
                }
            }
        },
        "Memory": {
            "Alert 1": {
                "condition1": {
                    "attribute": "nrqlQuery",
                    "operator": "CONTAINS",
                    "values": "memoryUsedPercent"
                },
                "condition2": {
                    "attribute": "policyName",
                    "operator": "NOT_CONTAINS",
                    "values": "CPU-Mem"
                }
            },
            "Alert 2": {
                "condition1": {
                    "attribute": "policyName",
                    "operator": "CONTAINS",
                    "values": "Standard_Server"
                },
                "condition2": {
                    "attribute": "conditionName",
                    "operator": "CONTAINS",
                    "values": "Memory"
                }
            }
        }
    }

    rule_template_one_cond = Template("""
    mutation mutingRuleCreate {
      alertsMutingRuleCreate(
        accountId: $account_id
        rule: {
          condition: {
            conditions: {
                attribute: "$att1",
                operator: $op1,
                values: "$val1"
            },
            operator: AND
          }, 
          description: "Mute $metric utilization alerts for values under 100 percent.", 
          enabled: true, 
          name: "Mute $metric alerts < 100 Percent #$number", 
          schedule: {
            repeat: DAILY, 
            timeZone: "America/Denver", 
            startTime: "2023-08-22T00:00:00", 
            endTime: "2023-08-22T23:59:59"
          }
        }
      ) {
        id
      }
    }
    """)

    rule_template_two_cond = Template("""
    mutation mutingRuleCreate {
      alertsMutingRuleCreate(
        accountId: $account_id
        rule: {
          condition: {
            conditions: [
              {
                attribute: "$att1",
                operator: $op1,
                values: "$val1"
              },
              {
                attribute: "$att2",
                operator: $op2,
                values: "$val2"
              }
            ],
            operator: AND
          }, 
          description: "Mute $metric utilization alerts for values under 100 percent.", 
          enabled: true, 
          name: "Mute $metric alerts < 100 Percent #$number", 
          schedule: {
            repeat: DAILY, 
            timeZone: "America/Denver", 
            startTime: "2023-08-22T00:00:00", 
            endTime: "2023-08-22T23:59:59"
          }
        }
      ) {
        id
      }
    }
    """)

    for metric, alerts in rules_dict.items():
        logger.info(f'Creating muting rules for {metric} utilization:')
        for alert, conditions in alerts.items():
            conditions_list = [condition for _, condition in conditions.items()]
            # logger.info(conditions_list)
            att_one = conditions_list[0]["attribute"]
            op_one = conditions_list[0]["operator"]
            val_one = conditions_list[0]["values"]
            number = alert[-1]
            # logger.info(att_one)
            if len(conditions_list) > 1:
                att_two = conditions_list[1]["attribute"]
                op_two = conditions_list[1]["operator"]
                val_two = conditions_list[1]["values"]
                rule_template_fmtd = rule_template_two_cond.substitute({"account_id": account_id,
                                                                        "metric": metric,
                                                                        "att1": att_one,
                                                                        "op1": op_one,
                                                                        "val1": val_one,
                                                                        "att2": att_two,
                                                                        "op2": op_two,
                                                                        "val2": val_two,
                                                                        "number": number})
                nr_response = requests.post(endpoint,
                                            headers=headers,
                                            json={"query": rule_template_fmtd}).json()
                # logger.info(f"New Relic API response:\n{nr_response}")
            else:
                rule_template_fmtd = rule_template_one_cond.substitute({"account_id": account_id,
                                                                        "metric": metric,
                                                                        "att1": att_one,
                                                                        "op1": op_one,
                                                                        "val1": val_one,
                                                                        "number": number})
                nr_response = requests.post(endpoint,
                                            headers=headers,
                                            json={"query": rule_template_fmtd}).json()
                # logger.info(f"New Relic API response:\n{nr_response}")
            logger.info(f'   Muting rule {nr_response["data"]["alertsMutingRuleCreate"]["id"]} {metric} '
                        f'#{number} created.')
