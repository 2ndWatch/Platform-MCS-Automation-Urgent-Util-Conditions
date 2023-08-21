import requests
import logging
from datetime import datetime
from string import Template
import sys
import create_conditions as cc


def initialize_logger():
    logger = logging.getLogger()
    logging.basicConfig(level=logging.INFO,
                        filename=f'urgent_conditions_{datetime.now().strftime("%Y-%m-%d_%H%M%S")}.log',
                        filemode='a')
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.INFO)
    logger.addHandler(console)

    return logger


def get_nr_account_ids(endpoint, headers):

    # response['data']['actor']['accounts'] (list of accounts)
    # account keys: 'id', 'name'
    nr_gql_accounts_query = Template("""
    {
      actor {
        accounts {
          id
          name
        }
      }
    }
    """)

    accounts_query_fmtd = nr_gql_accounts_query.substitute({})
    nr_response = requests.post(endpoint,
                                headers=headers,
                                json={'query': accounts_query_fmtd}).json()
    # logger.info(f'New Relic API response:\n{type(nr_response)}')

    return nr_response


def main():
    logger = initialize_logger()
    logger.info('Starting the policy and condition creation process.')

    endpoint = 'https://api.newrelic.com/graphql'
    headers = {
        'Content-Type': 'application/json',
        'API-Key': 'NRAK-7DVT82DILPFIAXSZZ6CLPKYB8YU',
    }

    accounts = get_nr_account_ids(endpoint, headers)

    # TODO: double-check excluded accounts
    # TODO: add Tooling-Test 3720977 back in when running for prod
    # 2W-MCS-Development, 2W-MCS-Internal-IT, 2W-MCS-Sandboxes, 2W-MCS-SiriusPoint-AWS, 2W-MCS-Tooling-Test,
    # 2W-MCS-Sysco-Azure, 2W-MCS-Sysco-GCP, 2W-MCS-AutoNation, 2nd Watch Partner,
    # 2W-MCS-PrudentPublishing (duplicate?), 2W-MCS-TitleMax, 2W-PRO-Development
    account_exclude_list = [2804528, 3719648, 2631905, 3498029, 3563046, 3563050,
                            2726097, 2563179, 3589554, 2623152, 2824352]
    accounts_list = accounts['data']['actor']['accounts']
    accounts_sorted = sorted(accounts_list, key=lambda x: x['name'])

    # testing
    accounts_sorted = [{"id": 3720977, "name": "2W-MCS-Tooling-Test"}]

    for account in accounts_sorted:
        account_id = account['id']
        client_name = account['name']

        if account_id not in account_exclude_list:
            logger.info(f'\n-----\nProcessing {client_name} in NR account {account_id}...\n-----\n')
            policy_id = cc.create_policy(endpoint, headers, account_id, logger)
            if policy_id != 1:
                cc.create_conditions(endpoint, headers, account_id, policy_id, logger)
                workflow_id, filter_id, values_list = cc.get_platform_workflow(endpoint, headers, account_id, logger)
                if values_list:
                    values_list.append(str(policy_id))
                    logger.info(f'Policy ID added to workflow associated policies:\n'
                                f'   {values_list}')
                    cc.update_workflow(endpoint, headers, account_id, policy_id, workflow_id, filter_id, values_list,
                                       logger)
                else:
                    logger.info(f'Something went wrong while trying to retrieve the Platform workflow.')
            else:
                logger.info(f'Something went wrong while trying to create the utilization alert policy.')
        else:
            logger.info(f'\n-----\n{client_name} is in the excluded accounts list; skipping this account.\n-----\n')


main()
