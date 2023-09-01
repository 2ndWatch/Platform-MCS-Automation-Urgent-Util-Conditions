from string import Template
import requests
from datetime import datetime, timedelta


def epoch_time_ms():
    today_dt = datetime.today()
    # print(today_dt)
    today_list = today_dt.strftime('%Y-%m-%d').split('-')

    today = round(datetime(int(today_list[0]), int(today_list[1]), int(today_list[2])).timestamp() * 1000)
    # print(f'Today: {today}')

    seven_days_dt = today_dt - timedelta(days=7)
    seven_days_list = seven_days_dt.strftime('%Y-%m-%d').split('-')

    seven_days = round(datetime(int(seven_days_list[0]), int(seven_days_list[1]),
                                int(seven_days_list[2])).timestamp() * 1000)
    # print(f'One week ago: {seven_days}')

    return today, seven_days


def get_issue_count(endpoint, headers, client_name, account_id, issues_df, logger):
    logger.info('Collecting issue data...')
    today, seven_days = epoch_time_ms()

    conditions = ['CPU_Utilization_100', 'Memory_Utilization_100']
    conditions_test = ['CPU', 'Memory']

    issue_template = Template("""
        {
          actor {
            account(id: $account_id) {
              aiIssues {
                issues(
                  filter: {contains: "$condition"}
                  timeWindow: {startTime: $start, endTime: $end}
                  cursor: "$cursor"
                ) {
                  issues {
                    conditionName
                  }
                  nextCursor
                }
              }
            }
          }
        }
        """)

    cpu_issues = 0
    memory_issues = 0

    # TODO: change conditions_test to conditions for prod
    for condition in conditions:
        is_cursor = True
        cursor = ''

        while is_cursor:

            issue_template_fmtd = issue_template.substitute({'account_id': account_id,
                                                             'condition': condition,
                                                             'start': seven_days,
                                                             'end': today,
                                                             'cursor': cursor})
            nr_response = requests.post(endpoint,
                                        headers=headers,
                                        json={'query': issue_template_fmtd}).json()

            # print(nr_response)
            issue_count = len(nr_response['data']['actor']['account']['aiIssues']['issues']['issues'])

            # TODO: change 'CPU' to 'CPU_Utilization_100' for production
            if condition == 'CPU':
                cpu_issues += issue_count
                print(f'   {cpu_issues} {condition} issue(s) found.')
            else:
                memory_issues += issue_count
                print(f'   {memory_issues} {condition} issue(s) found.')

            if nr_response['data']['actor']['account']['aiIssues']['issues']['nextCursor']:
                cursor = nr_response['data']['actor']['account']['aiIssues']['issues']['nextCursor']
            else:
                is_cursor = False

    row = [client_name, cpu_issues, memory_issues]
    issues_df.loc[len(issues_df)] = row

    return issues_df
