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


def generate_report(endpoint, headers, account_id, logger):
    logger.info('Collecting issue data...')

    # TODO: change issue filter as needed
    # Utilization_100
    issue_template = Template("""
        {
          actor {
            account(id: $account_id) {
              aiIssues {
                issues(
                  filter: {contains: "CPU"}
                  timeWindow: {startTime: $start, endTime: $end}
                ) {
                  issues {
                    conditionName
                    policyName
                    entityNames
                  }
                }
              }
            }
          }
        }
        """)

    today, seven_days = epoch_time_ms()

    issue_template_fmtd = issue_template.substitute({'account_id': account_id,
                                                     'start': seven_days,
                                                     'end': today})
    nr_response = requests.post(endpoint,
                                headers=headers,
                                json={'query': issue_template_fmtd}).json()

    # print(nr_response)
    issue_count = 0

    for issue in nr_response['data']['actor']['account']['aiIssues']['issues']['issues']:
        issue_count += 1

    print(f'   {issue_count} CPU issue(s) found.')
