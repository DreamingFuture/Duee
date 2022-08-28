# Copyright (c) 2021 Baidu.com, Inc. All Rights Reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""duee 1.0 data predict post-process"""

import argparse
import json

from utils.utils import read_by_lines, write_by_lines, extract_result

def get_type(pred_event_trigger):
    trigger_type = []
    role_type = []
    for item in pred_event_trigger:
        item = json.loads(item)
        trigger_type.append(item['event_type'])
        role_type += [ role['role'] for role in item['role_list']]
    return trigger_type, role_type

def predict_data_process(trigger_file, role_file, schema_file, save_path):
    """predict_data_process"""
    pred_ret = []
    trigger_datas = read_by_lines(trigger_file)
    role_data = read_by_lines(role_file)
    schema_datas = read_by_lines(schema_file)
    trigger_types, role_types = get_type(schema_datas)
    print("trigger predict {} load from {}".format(len(trigger_datas), trigger_file))
    print("role predict {} load from {}".format(len(role_data), role_file))
    print("schema {} load from {}".format(len(schema_datas), schema_file))

    schema = {}
    for s in schema_datas:
        d_json = json.loads(s)
        schema[d_json["event_type"]] = [r["role"] for r in d_json["role_list"]]

    # process the role data
    sent_role_mapping = {}
    for d in role_data:
        d_json = json.loads(d)
        r_ret = extract_result(d_json["text"], d_json["pred"]["labels"])
        role_ret = {}
        for r in r_ret:
            role_type = r["type"]
            if role_type not in role_types:
                continue
            if role_type not in role_ret:
                role_ret[role_type] = []
            role_ret[role_type].append("".join(r["text"]))
        sent_role_mapping[d_json["id"]] = role_ret

    for d in trigger_datas:
        d_json = json.loads(d)
        t_ret = extract_result(d_json["text"], d_json["pred"]["labels"])
        
        # 保证pred_event_types里都是schema里面的事件类型，防止role进入
        pred_event_types = []
        temp = list(set([t["type"] for t in t_ret]))
        for item in temp:
            if item in trigger_types:
                pred_event_types.append(item)
        pred_event_trigger = dict()
        for t in t_ret:
            # if t["type"] not in trigger_types:
            #     continue
            if t["type"] in pred_event_trigger:
                pred_event_trigger[t["type"]] += ''.join(t["text"])
            else:
                pred_event_trigger[t["type"]] = ''.join(t["text"])
        event_list = []
        for event_type in pred_event_types:  # 只有trigger触发了，对应的论元才会写到结果表中
            role_list = schema[event_type]
            arguments = []
            for role_type, ags in sent_role_mapping[d_json["id"]].items():
                if role_type not in role_list:
                    continue
                for arg in ags:
                    if len(arg) == 1:
                        continue
                    arguments.append({"role": role_type, "argument": arg})
            event = {"event_type": event_type,"trigger": pred_event_trigger[event_type], "arguments": arguments}
            event_list.append(event)
        pred_ret.append({
            "id": d_json["id"],
            "text": d_json["text"],
            "event_list": event_list
        })
    pred_ret = [json.dumps(r, ensure_ascii=False) for r in pred_ret]
    print("submit data {} save to {}".format(len(pred_ret), save_path))
    write_by_lines(save_path, pred_ret)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Official evaluation script for DuEE version 1.0")
    parser.add_argument(
        "--trigger_file", help="trigger model predict data path", required=True)
    parser.add_argument(
        "--role_file", help="role model predict data path", required=True)
    parser.add_argument("--schema_file", help="schema file path", required=True)
    parser.add_argument("--save_path", help="save file path", required=True)
    args = parser.parse_args()
    predict_data_process(args.trigger_file,
                         args.role_file,
                         args.schema_file,
                         args.save_path)
