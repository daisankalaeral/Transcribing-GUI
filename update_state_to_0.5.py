import subprocess
import json
import os
import argparse
from tqdm import tqdm

ffprobe_bin = "bin/" if os.path.isfile("bin/ffprobe.exe") else ""

def get_details(file):
    p = subprocess.Popen(fr'{ffprobe_bin}ffprobe -i "{file}" -show_entries stream=duration,sample_rate,sample_fmt,channels,duration -hide_banner',stdout=subprocess.PIPE,stderr = subprocess.PIPE,universal_newlines=True)
    stream = p.stdout.readlines()
    n_bits = int(stream[1].replace('sample_fmt=s', ''))
    sample_rate = int(stream[2].replace('sample_rate=', ''))
    channels = int(stream[3].replace('channels=', ''))
    duration = float(stream[4].replace('duration=', ''))
    return n_bits, sample_rate, channels, duration

def main():
    parser = argparse.ArgumentParser(usage = "Kill me")
    parser.add_argument("--input", "-i",  type = str, default = "bin/state.json", help = "Json path")
    parser.add_argument("--output", "-o", type = str, default = "output.json", help = "Output path")
    args = parser.parse_args()

    with open(args.input, 'r', encoding = 'utf-8') as file:
        json_data = json.loads(file.read())
    
    for id, files in tqdm(json_data['id'].items()):
        for file in files:
            file_path = json_data['id'][id][file]['path']
            if not os.path.isfile(file_path):
                print(file_path)
                continue
            n_bits, sample_rate, channels, duration = get_details(file_path)
            json_data['id'][id][file].update({
                'n_bits': n_bits,
                'sample_rate': sample_rate,
                'channels': channels,
                'duration': duration
            })
    
    with open(args.output, 'w', encoding = 'utf-8') as file:
        json.dump(json_data, file, indent = 4, ensure_ascii = False)
if __name__ == '__main__':
    main()