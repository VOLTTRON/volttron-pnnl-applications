from pathlib import Path

import gevent

from volttron.platform.vip.agent.utils import build_agent

base_topic = "devices/campus/building/rtu4"
datafile = Path(__file__).parent / "sample_data.csv"

agent = build_agent(identity="my-agent",
                    publickey="REpJn2gAaKKX7qDzN5M-NW8ZGmdJyPb-ggRDUd_K52Q",
                    secretkey="Lj8nDCqwkAb-dul7IhmeBQsE0jKv2fM2YaPgcmf0CBo",
                    serverkey="SzUeEpdkAu2qssziu-Etz2Is6hxt9oQy8rmFVoUxQ3s")

headers = []
data = {}

TIME_BETWEEN_LINES = 0.5
TIME_BETWEEN_FILES = 10
EXIT_AFTER_ONE = True

try:
    while True:
        for line in datafile.read_text().split("\n"):
            if not headers:
                headers = line.strip().split(",")
                continue
            columns = line.strip().split(",")
            ts = 0
            if len(columns) != len(headers):
                break

            # skip the notes column at the end.
            for i in range(len(columns[:-1])):
                if i == 0:
                    ts = columns[i]
                else:
                    try:
                        data[headers[i]] = float(columns[i])
                    except ValueError:
                        print(f"COULDN'T transform float column {i}")

            agent.vip.pubsub.publish(peer="pubsub",
                                     topic=f"{base_topic}/all",
                                     headers=dict(Date=ts),
                                     message=[data, {}])
            # publish here
            print(f"Publishing: {base_topic}/all, message=[data, {{}}] {data}")
            print(f"Note is: {columns[-1]}")
            input("Press enter to continue.")
            gevent.sleep(TIME_BETWEEN_LINES)
        if EXIT_AFTER_ONE:
            break
        print(f"Sleep before starting the file again!")
        gevent.sleep(TIME_BETWEEN_FILES)
except KeyboardInterrupt:
    pass
finally:
    agent.core.stop()
    gevent.sleep(1)
