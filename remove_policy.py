from string import Template
import requests
import json


def find_remove_policy(endpoint, headers, account_id, logger):
    logger.info('Searching for 2W-CPU-Mem-100 alert policy...')
    policy_search_template = Template("""
    {
      actor {
        account(id: $account_id) {
          alerts {
            policiesSearch {
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

    policy_search_fmtd = policy_search_template.substitute({"account_id": account_id})

    nr_response = requests.post(endpoint,
                                headers=headers,
                                json={'query': policy_search_fmtd}).json()

    policy_list = nr_response['data']['actor']['account']['alerts']['policiesSearch']['policies']

    policy_id = 0

    for policy in policy_list:
        if policy['name'] == '2W-CPU-Mem-100':
            policy_id = policy['id']

    logger.info(f'   Policy found, ID: {policy_id}')

    policy_delete_template = Template("""
    mutation {
      alertsPolicyDelete(accountId: $account_id, id: $policy_id) {
        id
      }
    }
    """)

    policy_delete_fmtd = policy_delete_template.substitute({"account_id": account_id,
                                                            "policy_id": policy_id})

    nr_response = requests.post(endpoint,
                                headers=headers,
                                json={'query': policy_delete_fmtd}).json()

    if nr_response['data']['alertsPolicyDelete']['id'] == policy_id:
        logger.info(f'   Policy ID {policy_id} deleted successfully.')
