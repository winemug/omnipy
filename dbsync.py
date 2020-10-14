import time
from pymongo import MongoClient
from mongo_sucks import mongo_find
import glob
import simplejson as json
import sqlite3

class DbSyncer:

    def __init__(self, bulk_path, current_pod_db_path):
        with open("settings.json", "r") as stream:
            self.settings = json.load(stream)
        self.current_pod_id = None
        self.current_pod_rowid = None
        self.bulk_path = bulk_path
        self.current_pod_db_path = current_pod_db_path

    def run(self):
        print("running bulk import")
        self.bulk_import()
        print("now watching")
        print(f'Current pod: {self.current_pod_id} Last synced id: {self.current_pod_rowid}')
        while True:
            time.sleep(10)
            try:
                ret = self.import_db(self.current_pod_db_path, False)
                if ret is not None:
                    pod_id, row_id = ret
                    if pod_id != self.current_pod_id:
                        print(f"Pod change detected - running bulk import")
                        self.bulk_import()
                    if pod_id != self.current_pod_id or row_id != self.current_pod_rowid:
                        self.current_pod_id, self.current_pod_rowid = ret
                        print(f'Current pod: {self.current_pod_id} Last synced id: {self.current_pod_rowid}')

            except Exception as e:
                print("Error importing: %s" % e)
                time.sleep(120)

    def bulk_import(self):
        for db_path in glob.glob(self.bulk_path + "/*.db"):
            try:
                abandoned = db_path != self.current_pod_db_path
                ret = self.import_db(db_path, abandoned)
                if not abandoned and ret is not None:
                    self.current_pod_id, self.current_pod_rowid = ret

            except Exception as e:
                print(f'Skipping {db_path} due error: {e}')

    def import_db(self, db_path: str, abandoned: bool, last_row_id: int = None, last_pod_id: str = None):
        mongo_uri = self.settings["mongo_url"]
        pod_id = None
        with sqlite3.connect(db_path) as conn:
            try:
                cursor = None
                sql = "SELECT rowid, timestamp, pod_json FROM pod_history WHERE pod_state > 0"
                cursor = conn.execute(sql)
                sqlite_rows = cursor.fetchall()
            finally:
                if cursor is not None:
                    cursor.close()

        if sqlite_rows is not None and len(sqlite_rows) > 0:
            js = json.loads(sqlite_rows[0][2])
            if "pod_id" not in js or js["pod_id"] is None:
                pod_id = "L" + str(js["id_lot"]) + "T" + str(js["id_t"])
            else:
                pod_id = js["pod_id"]

        if pod_id is None:
            print("No pod seems to be registered on %s" % db_path)
            return None

        if last_pod_id is not None and last_pod_id != pod_id:
            last_row_id = None

        with MongoClient(mongo_uri) as mongo_client:
            db = mongo_client.get_database("nightscout")
            coll_pod_entries = db.get_collection("omnipy")
            coll_pods = db.get_collection("pods")

            id_list = None
            if last_row_id is None:
                id_entries = mongo_find(coll_pod_entries, {'pod_id': pod_id}, projection=['last_command_db_id'])
                id_list = [e['last_command_db_id'] for e in id_entries]

            first_success_ts = None
            last_success_ts = None
            start_ts = None
            deactivate_ts = None
            fault_ts = None
            total_delivered = 0.0
            fault_code = None

            entry_added = False
            for row in sqlite_rows:
                last_db_id = row[0]
                if row[2] is None:
                    continue

                if last_row_id is not None and row[0] <= last_row_id:
                    continue

                js = json.loads(row[2])
                if "data" in js:
                    js = js["data"]

                js["pod_id"] = pod_id
                js["last_command_db_id"] = row[0]
                js["last_command_db_ts"] = row[1]

                if not row[0] in id_list:
                    coll_pod_entries.insert_one(js)
                    entry_added = True

                if "insulin_delivered" not in js:
                    pass
                total_delivered = js["insulin_delivered"]

                if js["state_faulted"] and fault_ts is None:
                    fault_code = js["fault_event"]
                    current_minute = js["state_active_minutes"]
                    faulted_at = js["fault_event_rel_time"]
                    fault_ts = row[1] - (current_minute - faulted_at + 1) * 60

                lc = js["last_command"]
                if lc is not None and lc["success"]:
                    if first_success_ts is None:
                        first_success_ts = row[1]
                    last_success_ts = row[1]
                    if lc["command"] == "DEACTIVATE" and deactivate_ts is None:
                        deactivate_ts = row[1]
                    if lc["command"] == "START" and start_ts is None:
                        if js["var_activation_date"] is not None:
                            start_ts = js["var_activation_date"]
                        else:
                             start_ts = row[1]

            cursor.close()
            if entry_added:
                pod = coll_pods.find_one({'pod_id': pod_id})
                new_pod = False
                if pod is None:
                    new_pod = True
                    pod = dict()
                pod['pod_id'] = pod_id
                if start_ts is None:
                    pod["start"] = first_success_ts
                else:
                    pod["start"] = start_ts

                pod["abandoned"] = False

                if fault_ts is not None:
                    pod["end"] = fault_ts
                elif deactivate_ts is not None:
                    pod["end"] = deactivate_ts
                elif abandoned:
                    pod["end"] = last_success_ts
                    pod["abandoned"] = True
                else:
                    pod["end"] = None

                pod["delivered"] = total_delivered
                pod["fault_code"] = fault_code
                pod["last_rowid"] = last_db_id

                if new_pod:
                    coll_pods.insert_one(pod)
                else:
                    coll_pods.replace_one(pod, pod)

            return pod_id, last_db_id


if __name__ == '__main__':
    dbs = DbSyncer('/home/pi/omnipy/data', '/home/pi/omnipy/data/pod.db')
    while True:
        dbs.run()
