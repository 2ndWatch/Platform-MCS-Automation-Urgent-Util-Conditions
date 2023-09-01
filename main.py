import requests
import logging
from datetime import datetime
from string import Template
import sys
import create_conditions as cc
import create_muting_rules as mr
import generate_issue_report as ir
import remove_policy as rp
import pandas as pd
import openpyxl
from UliPlot.XLSX import auto_adjust_xlsx_column_width as adjust


def initialize_logger():
    logger = logging.getLogger()
    logging.basicConfig(level=logging.INFO,
                        filename=f'urgent_conditions_{datetime.now().strftime("%Y-%m-%d_%H%M%S")}.log',
                        filemode='a')
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.INFO)
    logger.addHandler(console)

    return logger


def get_nr_account_ids(endpoint, headers, logger):
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
    # logger.info(f'New Relic API response:\n{nr_response}')

    return nr_response


def main():
    logger = initialize_logger()
    logger.info('Starting the muting rules, policy and condition creation process.')

    endpoint = 'https://api.newrelic.com/graphql'
    headers = {
        'Content-Type': 'application/json',
        'API-Key': '',
    }

    accounts = get_nr_account_ids(endpoint, headers, logger)

    # 2W-MCS-Development, 2W-MCS-Internal-IT, 2W-MCS-Sandboxes, 2W-MCS-Tooling-Test,
    # 2W-MCS-AutoNation, 2nd Watch Partner, 2W-MCS-PrudentPublishing (duplicate?), 2W-MCS-TitleMax,
    # 2W-PRO-Development, 2W-MCS-notifications-channel-test
    account_exclude_list = [2804528, 3719648, 2631905, 3720977, 2726097, 2563179, 3589554, 2623152, 2824352, 3773323]
    accounts_list = accounts['data']['actor']['accounts']
    accounts_sorted = sorted(accounts_list, key=lambda x: x['name'])

    # testing
    # accounts_sorted = [{"id": 2659483, "name": "2W-MCS-Sysco"},
    #                    {"id": 3324386, "name": "2W-MCS-UtilitiesInternational"}]

    # accounts_sorted_batch_test = [{"id": 2621186, "name": "2W-MCS-2ndWatch"},
    #                               {"id": 2672105, "name": "2W-MCS-Aperio"},
    #                               {"id": 2709554, "name": "2W-MCS-Cargill"}]

    initial_issues_df = pd.DataFrame(columns=['Client Name', 'All CPU Issues', 'All Memory Issues'])
    issues_df = pd.DataFrame(columns=['Client Name', 'CPU 100% Issues', 'Memory 100% Issues'])

    for account in accounts_sorted:
        account_id = account['id']
        client_name = account['name']

        if account_id not in account_exclude_list:
            logger.info(f'\n-----\nProcessing {client_name} in NR account {account_id}...\n-----\n')

            # rp.find_remove_policy(endpoint, headers, account_id, logger)

            # mr.create_muting_rules(endpoint, headers, account_id, logger)

            policy_id = cc.create_policy(endpoint, headers, account_id, logger)
            if policy_id != 1:
                cc.create_conditions(endpoint, headers, account_id, policy_id, logger)
                # workflow_id, filter_id, values_list = cc.get_platform_workflow(endpoint, headers, account_id, logger)
                # if values_list:
                #     values_list.append(str(policy_id))
                #     logger.info(f'Policy ID added to workflow associated policies:\n'
                #                 f'   {values_list}')
                #     cc.update_workflow(endpoint, headers, account_id, policy_id, workflow_id, filter_id, values_list,
                #                        logger)
                # else:
                #     logger.info(f'Something went wrong while trying to retrieve the Platform workflow.')
            # else:
            #     logger.info(f'Something went wrong while trying to create the utilization alert policy.')

            # ir.get_issue_count(endpoint, headers, client_name, account_id, initial_issues_df, logger)

        else:
            logger.info(f'\n-----\n{client_name} is in the excluded accounts list; skipping this account.\n-----\n')

    # try:
    #     with pd.ExcelWriter(f'CPU Mem Issues Past 30 Days {datetime.today().date()}.xlsx',
    #                         mode='a', if_sheet_exists='replace') as writer:
    #         initial_issues_df.to_excel(writer, sheet_name=f'Issues', index=False)
    #         adjust(initial_issues_df, writer, sheet_name=f'Issues', margin=3, index=False)
    # except FileNotFoundError:
    #     with pd.ExcelWriter(f'CPU Mem Issues Past 30 Days {datetime.today().date()}.xlsx') as writer:
    #         initial_issues_df.to_excel(writer, sheet_name=f'Issues', index=False)
    #         adjust(initial_issues_df, writer, sheet_name=f'Issues', margin=3, index=False)


# TODO: module to detect and disable CPU and memory muting rules

# 2W-CPU-Mem-100-test workflow

main()
