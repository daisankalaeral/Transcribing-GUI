import argparse
import json
import os
import re
import random
import shutil

def copy_file(sv, src_path, output_dir, mark):
    txt_src_path = os.path.splitext(src_path)[0] + '.txt'
    src_name = os.path.basename(src_path)
    txt_src_name = os.path.basename(txt_src_path)
    dest_dir = f'{output_dir}/{mark}/{sv}/'
    os.makedirs(dest_dir, exist_ok=True)
    dest_path = f'{dest_dir}/{src_name}'
    txt_dest_path = f'{dest_dir}/{txt_src_name}'
    shutil.copy(src_path, dest_path)
    shutil.copy(txt_src_path, txt_dest_path)

def main():
    parser = argparse.ArgumentParser(usage = "Kill me")
    parser.add_argument("--input", "-i",  type = str, default = "bin/state.json", help = "Json path")
    parser.add_argument("--output", "-o", type = str, default = "double_checked", help = "Output directory")
    args = parser.parse_args()

    output_dir = args.output

    with open(args.input, 'r', encoding = 'utf-8') as file:
        json_data = json.loads(file.read())
    
    sv_dict = {}

    for id, files in json_data['id'].items():
        sv_dict[id] = {}
        for file, content in files.items():
            temp = content['path']
            dir = re.split(r'\\|/', temp)[-2]
            sv_dict[id].setdefault(dir, {})
            sv_dict[id][dir].update({
                file: content
            })
    
    for sv in sv_dict:
        temp = json_data['id'][sv]

        first_10 = list(file for file in json_data['id'][sv] if json_data['id'][sv][file]['accepted'])[:10]
        if first_10:
            for file in first_10:
                src_path = json_data['id'][sv][file]['path']
                copy_file(sv, src_path, output_dir, 'accepted')

        for dir in sv_dict[sv]:
            accepted_list = list(file for file in sv_dict[sv][dir] if (sv_dict[sv][dir][file]['accepted'] and sv_dict[sv][dir][file] not in first_10))
            not_accepted_list = list(file for file in sv_dict[sv][dir] if (not sv_dict[sv][dir][file]['accepted'] and sv_dict[sv][dir][file] not in first_10))
            # try:
            if accepted_list:
                choice = random.choice(accepted_list)
                src_path = sv_dict[sv][dir][choice]['path']
                copy_file(sv, src_path, output_dir, 'accepted')
            if not_accepted_list:
                choice = random.choice(not_accepted_list)
                src_path = sv_dict[sv][dir][choice]['path']
                copy_file(sv, src_path, output_dir, 'not_accepted')
            # except Exception as e:
            #     print(e)
            #     continue

if __name__ == '__main__':
    main()