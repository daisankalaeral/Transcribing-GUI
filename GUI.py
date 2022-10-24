import tkinter as tk
from tkinter.constants import ACTIVE, END, EXTENDED, HORIZONTAL, INSERT, WORD
from tkinter import ANCHOR, DISABLED, NORMAL, W, filedialog
import tkinter.ttk as ttk
import subprocess
import os 
import json
import vlc
import speech_recognition as sr
from PIL import Image, ImageTk
import re
from tqdm import tqdm
# import shutil
import Levenshtein as Lev
from datetime import datetime

ffprobe_bin = "bin/" if os.path.isfile("bin/ffprobe.exe") else ""

def char_distance(ref, hyp):
    ref = ref.replace(' ', '').upper()
    hyp = hyp.replace(' ', '').upper()

    dist = Lev.distance(hyp, ref)
    length = len(ref)

    return dist, length 

r = sr.Recognizer()
if os.path.isfile('bin/state.json'):
    with open('bin/state.json', 'r+', encoding = 'utf-8') as file:
        json_data = json.loads(file.read())
else:
    with open('bin/state.json', 'w', encoding = 'utf-8') as file:
        json_data = {
            'volume': 100,
            'audio_paths': [],
            'id': {}
        }

font_size = 14
rate = 1
root = tk.Tk()
root.resizable(True, True)
root.columnconfigure(0, weight=1)
root.rowconfigure(2, weight = 1)
root.rowconfigure(5, weight = 1)
root.title('GUI x' + str(rate))
root.config(bg = '#36393f')
root.call('wm', 'iconphoto', root._w, tk.PhotoImage(file = fr"img\MBTL_faq_icon.png"))

s = ttk.Style()

if root.getvar('tk_patchLevel')=='8.6.9': #and OS_Name=='nt':
    def fixed_map(option):
        return [elm for elm in s.map('Treeview', query_opt=option) if elm[:2] != ('!disabled', '!selected')]
    s.map('Treeview', foreground=fixed_map('foreground'), background=fixed_map('background'))
s.configure("TScale", background = '#36393f', foreground = 'red', fieldbackground = 'red')
s.configure("Treeview", background="cyan", foreground="#dcddde", fieldbackground="#dcddde", font = ('',11))
s.map("Treeview", foreground = [])
# Player
instance = vlc.Instance()
instance.log_unset()
player = instance.media_player_new()
player.audio_set_volume(json_data['volume'])

# Audio box
box_frame = tk.Frame(root)
box_frame.grid(row = 0, column = 0, sticky = 'ewsn')
box_frame.rowconfigure(0, weight = 1)
audio_box = tk.Listbox(box_frame, bg = '#282a36', fg="green", selectbackground="grey", selectmode=EXTENDED, exportselection=False)
audio_box.config(font=("Calibri",12))
audio_box.grid(row = 0, column = 0, sticky='ewsn')
scroll_bar = tk.Scrollbar(box_frame)
scroll_bar.grid(row = 0, column = 1, sticky = "sn")
audio_box.configure(yscrollcommand = scroll_bar.set)
scroll_bar.configure(command = audio_box.yview)
box_frame.columnconfigure(0,weight=1)

solve = None
marked = {}
active_file = ""
msv = ""
filename = ""
pause_check = 0
current_time = 0
total_duration = 0
focus = 0
id_count = 0

class new_tree(tk.Frame):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.pause_point = 0
        self.seg_play = False
        self.rowconfigure(0, weight = 1)
        self.treeview = ttk.Treeview(self)
        self.segments = {}
        self.json_path = ''
        self.if_overlap = {}
        self.scroll_bar = tk.Scrollbar(self)
        self.treeview.grid(row = 0, column = 0, sticky = 'sn')
        self.scroll_bar.grid(row = 0, column = 1, sticky = 'sn')
        self.treeview.configure(yscrollcommand = self.scroll_bar.set)
        self.scroll_bar.configure(command = self.treeview.yview)
        self.treeview.tag_configure('highlight', foreground = 'white')
        self.treeview.tag_configure('overlap', foreground = '#CA0B00')

        self.treeview['columns'] = ("Start", "End")
        self.treeview.column("#0", width = 1, anchor = W)
        self.treeview.column("Start", width = 100, anchor = W)
        self.treeview.column("End", width = 100, anchor = W)
        # self.treeview.column("Duration", width = 100, anchor = W)

        self.treeview.heading("Start", text = "Start", anchor = W)
        self.treeview.heading("End", text = "End", anchor = W)
        # self.treeview.heading("Duration", text = "Duration", anchor = W)
        
        self.treeview.bind('<Double-Button-1>', jump)
        # self.treeview.bind('<Motion>', self.highlight_row)
        bind_(self.treeview, modifier="Control", letter="g", callback=self.get_iid) #Control+m
        bind_(self.treeview, modifier="Control", letter="x", callback=self.remove_segments) #Control+m

    def highlight_row(self, event):
        iid = self.treeview.identify_row(event.y)
        self.treeview.tk.call(self.treeview, "tag", "remove", "highlight")
        self.treeview.tk.call(self.treeview, "tag", "add", ("highlight"), iid)

    def get_iid(self, event):
        print(self.treeview.selection()[0])
        print(self.segments[int(self.treeview.selection()[0])])

    def remove_segments(self, event):
        try:
            for row in self.treeview.selection():
                self.treeview.delete(row)
                del self.segments[int(row)]
            self.file_update()
        except Exception as e:
            pass
        
    def clear(self):
        self.pause_point = 0
        self.seg_play = False
        self.json_path = ''
        self.segments = {}
        self.if_overlap = {}
        tree.treeview.delete(*tree.treeview.get_children())

    def file_update(self):
        with open(self.json_path, 'w', encoding = 'utf-8') as file:
            json.dump(self.segments, file, ensure_ascii=False, indent = 4)

    def check_overlap(self):
        for i, v in self.segments.items():
            if v['End'] <= v['Start']:
                self.treeview.tk.call(self.treeview, "tag", "add", ("overlap"), i)
                self.if_overlap[i] = 1
                continue
            a = []
            b = []
            for j, k in self.segments.items():
                a.append(v['Start'] < k['End'])
                b.append(v['End'] > k['Start'])
            o = sum([g and h for g,h in zip(a,b)])
            if o > 1:
                self.treeview.tk.call(self.treeview, "tag", "add", ("overlap"), i)
                self.if_overlap[i] = 1
            else:
                self.treeview.tk.call(self.treeview, "tag", "remove", ("overlap"), i)
                self.if_overlap[i] = 0

class toplevel(tk.Toplevel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
    
def json_update():
    with open('bin/state.json', 'w', encoding = 'utf-8') as file:
        json.dump(json_data, file, ensure_ascii= False, indent = 4)

def audio_box_update(temp):
    global focus
    add_check = 0
    for i in temp:
        if i in marked:
            focus = 0
            audio_box.focus()
            audio_box.selection_clear(0, END)
            audio_box.selection_set(marked[i])
            audio_box.see(marked[i])
            audio_box.activate(marked[i])
            continue
        audio_box.insert(END, i)
        json_data['audio_paths'].append(i)
        marked[i] = len(marked)
        add_check = 1
    if add_check:
        json_update()
        focus = 0
        audio_box.focus()
        audio_box.selection_clear(0, END)
        audio_box.selection_set(END)
        audio_box.see(END)
        audio_box.activate(END)

def add_folder(x = None):
    folder_path = filedialog.askdirectory(title = "Select a folder")
    temp = []
    for roots, subdirs, files in os.walk(folder_path):
        for file in files:
            if file.endswith(('.mp3', '.wav', '.ogg', '.webm')):
                temp.append(f'{roots}/{file}')
    audio_box_update(sorted(temp))

def add_audio(x = None):
    audio_paths = filedialog.askopenfilenames(title = "Select audio files", filetypes=[("mp3 files","*.mp3"), ("wav files","*.wav"), ("all files","*.*")])
    audio_box_update(audio_paths)

def remove_audio(x = None):
    try:
        selection = audio_box.curselection()
        next = selection[0]
        for i in reversed(selection):
            if audio_box.get(i) == active_file:
                stop()
                text.delete('1.0', END)
                text_path_clear()
                # tree.clear()
            audio_box.delete(i)
            del marked[json_data['audio_paths'][i]]
            del json_data['audio_paths'][i]
        json_update()
        if next == audio_box.size():
            next -= 1
        audio_box.selection_set(next)
    except Exception as e:
        pass

def Ulnar_Wrist_Pain_Helppppp():
    save_button.config(text = 'Save')

def save(e = None):
    save_button.config(text = '......')
    t = text.get("1.0",END)[:-1]
    try:
        if transcript_mode.get():
            txt_path = text_path.get('1.0', END)[:-1]
            if os.path.exists(os.path.dirname(txt_path)) is False:
                os.makedirs(os.path.dirname(txt_path))
            with open(txt_path, 'w', encoding='utf-8') as file:
                file.write(t)
            if msv:
                distance, length = char_distance(t, json_data['id'][msv][filename]['original_text'])
                now = datetime.now()
                dt = now.strftime("%d/%m/%Y %H:%M:%S")
                json_data['id'][msv][filename].update({
                    'path': active_file,
                    'ref_text': t,
                    'comment': comment_text.get("1.0", END)[:-1],
                    'distance': distance,
                    'length': length,
                    'cer': (distance/length)*100 if length > 0 else "?",
                    'datetime': dt
                })
                json_update()
    except Exception as e:
        pass
    
    save_frame.after(500, Ulnar_Wrist_Pain_Helppppp)

def update_text_path(str = None):
    text_path.config(state=NORMAL)
    text_path.delete("1.0", END)
    text_path.insert(INSERT, str)
    text_path.config(state=DISABLED)

def text_path_clear():
    text_path.config(state=NORMAL)
    text_path.delete("1.0", END)
    text_path.config(state=DISABLED)

def load_text():
    if transcript_mode.get() and active_file:
        txt_path = os.path.splitext(active_file)[0] + '.txt'
        update_text_path(txt_path)
        text.delete("1.0", END)
        if os.path.isfile(txt_path) is True:
            with open(txt_path, 'r', encoding='utf-8') as file:
                text.insert(INSERT, file.read())

def load_eval():
    global eval
    if active_file in json_data["bad"]:
        switch_eval(x = 0)
    else:
        switch_eval(x = 1)

def load_para():
    comment_text.delete('1.0', END)
    global eval
    if msv:
        json_data['id'].setdefault(msv, {})
        if filename not in json_data['id'][msv]:
            txt_path = os.path.splitext(active_file)[0] + '.txt'
            if os.path.isfile(txt_path):
                with open(txt_path, 'r', encoding = 'utf-8') as file:
                    t = file.read()
            else:
                t = ""
            now = datetime.now()
            dt = now.strftime("%d/%m/%Y %H:%M:%S")
            n_bits, sample_rate, channels, duration = get_details(active_file)
            temp = {
                "path": active_file,
                "original_text": t,
                "ref_text": t,
                "comment": "",
                "distance": 0,
                "length": len(t.replace(' ', '')),
                "cer": 0.0,
                "datetime": dt,
                "accepted": 1,
                "n_bits": n_bits,
                "sample_rate": sample_rate,
                "channels": channels,
                "duration": duration
            }
            json_data['id'][msv][filename] = temp
            json_update()
            switch_eval(x = 1)
        else:
            comment_text.insert(INSERT, json_data['id'][msv][filename]['comment'])
            eval = json_data['id'][msv][filename]['accepted']
            json_data['id'][msv][filename]['path'] = active_file
            switch_eval(x = eval)
            

def load_segments():
    tree.clear()
    global id_count
    id_count = 0
    audio_path = audio_box.get(ACTIVE)
    tree.json_path = os.path.splitext(audio_path)[0] + '.json'
    if os.path.isfile(tree.json_path) is True:
        try:
            with open(tree.json_path, 'r', encoding = 'utf-8') as file:
                temp = file.read()
                tree.segments = json.loads(temp, object_hook=lambda d: {int(k) if k.lstrip('-').isdigit() else k: v for k, v in d.items()})
            for i, v in tree.segments.items():
                tree.treeview.insert('', END, iid = i, values = [sec2mmss(v['Start'], False), sec2mmss(v['End'], False)])
                id_count = i
            
            tree.treeview.selection_set(id_count)
            tree.treeview.focus(id_count)
            id_count += 1
            tree.check_overlap()
        except Exception as e:
            pass
    
import time
def export_segments():
    start = time.time()
    if player.get_state() == vlc.State.Playing:
        pause()
    command = r'ffmpeg -i "{}"'.format(active_file)
    
    filename_without_ext = os.path.basename(os.path.splitext(active_file)[0])
    dirname = os.path.dirname(active_file) + '/' + filename_without_ext
    target = dirname + '/' + filename_without_ext
    keys = [x for x in sorted(tree.segments, key = lambda x: tree.segments[x]['Start']) if  not tree.if_overlap[x]]
    os.makedirs(dirname, exist_ok = True)
    for i, k in enumerate(keys):
        command += ' -ss {} -to {} -sample_fmt s16 -ar 16000 -ac 1 "{}"'.format(tree.segments[k]['Start'], tree.segments[k]['End'], target + '_{:03}'.format(i) + '.wav')
    command += ' -y -hide_banner'
    subprocess.run(command, shell = True)
    end = time.time()
    print(f'Done ! Time taken: {sec2mmss(end-start, round = False)}')

def vlov():
    play_button['image'] = vlov1

def play(e = None):
    reset()
    play_button['image'] = vlov2
    global pause_check
    pause_check = 1
    audio_path = audio_box.get(ACTIVE)
    global active_file
    global msv
    global filename
    if not os.path.isfile(audio_path):
        bar.config(text = '')
        print('File does not exist !')
        play_button.after(500, vlov)
        return
    if active_file != audio_path:
        active_file = audio_path
        title = audio_path.split('/')[-1]
        filename = title
        msv = re.search('[a-zA-Z]\d{2}[a-zA-Z]{4}\d{3}', active_file)
        if msv:
            msv = msv.group().upper()
        else:
            msv = ''
        audio_title.config(text = title)
        load_text()
        # load_segments()
        load_para()
        # load_eval()
    player.set_media(vlc.Media(audio_path))
    global total_duration
    total_duration = get_duration(audio_path)
    slider.config(from_ = 0, to = int(total_duration), value = 0)
    pause_button['image'] = unpausesd_image
    player.play()
    play_time()
    play_button.after(500, vlov)

audio_box.bind('<Double-Button-1>', play)

def stop(e = None):
    player.stop()
    pause_button['image'] = paused_image
    audio_title.config(text = '')
    bar.config(text = '')
    slider.config(value = 0)
    global active_file
    active_file = ""
    global msv
    msv = ""
    global filename
    title = ""
    global pause_check
    pause_check = 0
    save_button.config(text = 'Save')
    if solve is not None:
        root.after_cancel(solve)

def reset():
    player.stop()
    # tree.seg_play = False
    save_button.config(text = 'Save')
    if solve is not None:
        root.after_cancel(solve)

def pause(e = None):
    global pause_check
    if pause_check == 1:
        pause_check = 0
        player.pause()
        pause_button['image'] = paused_image
        global solve
        if solve is not None:
            root.after_cancel(solve)
    elif pause_check == 0:
        pause_check = 1
        player.play()
        play_time()
        pause_button['image'] = unpausesd_image

def back(e = None):
    try:
        next = audio_box.curselection()[0] - 1
        if next < 0:
            next = audio_box.size() - 1
        audio_box.selection_clear(0, END)
        audio_box.activate(next)
        audio_box.selection_set(next)
        audio_box.see(next)
        play()
    except Exception as e:
        pass

def forward(e = None):
    try:
        next = audio_box.curselection()[0] + 1
        if next >= audio_box.size():
            next = 0
        audio_box.selection_clear(0, END)
        audio_box.activate(next)
        audio_box.selection_set(next)
        audio_box.see(next)
        play()
    except Exception as e:
        pass

def sec2mmss(sec, round = True):
    minutes = 0
    seconds = 0
    minutes = sec//60
    seconds = sec - minutes*60
    if round:
        return '{:02.0f}:{:02}'.format(minutes, int(seconds))
    else:
        return '{:02.0f}:{:06.3f}'.format(int(minutes), seconds)

def mmss2sec(str):
    mm, ss = str.split(':')
    return int(mm)*60 + float(ss)

def get_duration(file):
    p = subprocess.Popen(fr'{ffprobe_bin}ffprobe -i "{file}" -show_entries format=duration',stdout=subprocess.PIPE,stderr = subprocess.PIPE,universal_newlines=True)
    duration = float(p.stdout.readlines()[1].replace('duration=', ''))
    return duration

def get_details(file):
    p = subprocess.Popen(fr'{ffprobe_bin}ffprobe -i "{file}" -show_entries stream=duration,sample_rate,sample_fmt,channels,duration',stdout=subprocess.PIPE,stderr = subprocess.PIPE,universal_newlines=True)
    stream = p.stdout.readlines()
    n_bits = int(stream[1].replace('sample_fmt=s', ''))
    sample_rate = int(stream[2].replace('sample_rate=', ''))
    channels = int(stream[3].replace('channels=', ''))
    duration = float(stream[4].replace('duration=', ''))
    return n_bits, sample_rate, channels, duration

def play_time():
    global current_time
    current_time = player.get_position() * total_duration
    if player.get_state() == 6:
        slider.config(value = total_duration)
        bar.config(text = "{}/{}".format(sec2mmss(total_duration), sec2mmss(total_duration)))
        play()
    # elif tree.seg_play and current_time >= tree.pause_point:
    #     pause()
    #     slider.config(value = tree.pause_point)
    #     player.set_position(tree.pause_point/total_duration)
    #     tree.seg_play = False
    else:
        bar.config(text = "{}/{}".format(sec2mmss(current_time), sec2mmss(total_duration)))
        slider.config(value = current_time)
    if pause_check:
        global solve
        solve = root.after(50, play_time)

def set_value(event):
    slider.event_generate('<Button-3>', x=event.x, y=event.y)
    # print(1)
    return 'break'

def slide(x):
    slider_pos = slider.get()
    global solve
    if solve is not None:
        root.after_cancel(solve)
    player.set_position(slider_pos/total_duration)
    # tree.seg_play = False
    play_time()

def left(x):
    slider_pos = slider.get() - 2
    slider.config(value = slider_pos)
    global solve
    if solve is not None:
        root.after_cancel(solve)
    player.set_position(slider_pos/total_duration)
    # tree.seg_play = False
    play_time()

def right(x):
    slider_pos = slider.get() + 2
    slider.config(value = slider_pos)
    global solve
    if solve is not None:
        root.after_cancel(solve)
    player.set_position(slider_pos/total_duration)
    # tree.seg_play = False
    play_time()

def jump(e):
    rowid = e.y
    colid = e.x
    row = int(tree.treeview.identify_row(rowid))
    col = int(tree.treeview.identify_column(colid)[1:])
    if col == 2:
        slider_pos = tree.segments[row]['End']
        tree.seg_play = False
    else:
        tree.seg_play = True
        tree.pause_point = tree.segments[row]['End']
        slider_pos = tree.segments[row]['Start']
    slider.config(value = slider_pos)
    global solve
    if solve is not None:
        root.after_cancel(solve)
    player.set_position(slider_pos/total_duration)
    play_time()

def increase_volume(e = None):
    if json_data['volume'] < 100:
        json_data['volume'] += 2
        json_update()
        volume_label.config(text = str(json_data['volume']))
        player.audio_set_volume(json_data['volume'])
        volume_label.config(text = str(json_data['volume']))
        json_update()

def decrease_volume(e = None):
    if json_data['volume'] > 0:
        json_data['volume'] -= 2
        player.audio_set_volume(json_data['volume'])
        volume_label.config(text = str(json_data['volume']))
        json_update()

def speed_up(e = None):
    global rate
    if rate < 2:
        rate += 0.25
    player.set_rate(rate)
    root.title('GUI x' + str(rate))

def slow_down(e = None):
    global rate
    if rate > 0.25:
        rate -= 0.25
    player.set_rate(rate)
    root.title('GUI x' + str(rate))

def switch_focus(e = None):
    global focus
    if focus == 0:
        text.focus()
        focus = 1
    else:
        audio_box.focus()
        focus = 0

def delete_whole_word(e):
    ent = e.widget
    ent.delete("insert-1c wordstart", "insert")
    return "break"

def toggle_transcript(e = None):
    mode = transcript_mode.get()
    if mode:
        load_text()
        text_frame.grid(sticky = 'ewsn')
        # tree.grid(rowspan=6)
        # tree.scroll_bar.grid(rowspan = 6)
    else:
        text_path_clear()
        text_frame.grid_forget()
        # tree.grid(rowspan = 5)
        # tree.scroll_bar.grid(rowspan = 5)

def test_test(e = None):
    s = current_time
    global id_count
    # if len(tree.segments) >= 1:
    #     last = list(tree.segments)[-1]
    #     s = max(tree.segments[last]['End'], tree.segments[last]['Start'])
    # else:
    #     s = 0
    tree.segments[id_count] = {
        'Start': s,
        'End': total_duration
    }
    tree.last_end = total_duration
    tree.treeview.insert('', END, iid = id_count, values=[sec2mmss(tree.segments[id_count]['Start'], False), sec2mmss(tree.segments[id_count]['End'], False)])
    tree.treeview.selection_set(id_count)
    tree.treeview.focus(id_count)
    id_count += 1
    tree.file_update()
    tree.check_overlap()

def add_point(e, col):
    t = current_time
    focused = tree.treeview.focus()
    if not focused:
        test_test()
    focused = tree.treeview.focus()
    tree.segments[int(focused)][col] = t
    tree.treeview.set(focused, col, sec2mmss(t, False))
    tree.file_update()
    tree.check_overlap()

def mouse_wheel(event):
    global font_size
    # respond to Linux or Windows wheel event
    if event.num == 5 or event.delta == -120:
        if font_size > 14:
            font_size -= 1
    if event.num == 4 or event.delta == 120:
        font_size += 1
    text.config(font=("Calibri",font_size))
    comment_text.config(font=("Calibri",font_size))
    # text_path.config(font=("Calibri",font_size))

root.bind("<Control-MouseWheel>", mouse_wheel)

def speech_to_text(e = None):
    try:
        if active_file and transcript_mode.get():
            if player.get_state() == vlc.State.Playing:
                pause()
            print('Start Speech to Text !')
            with sr.AudioFile(active_file) as source:
                # listen for the data (load audio to memory)
                audio_data = r.record(source)
                # recognize (convert from speech to text)
                temp = r.recognize_google(audio_data, language = 'vi-VN')
                text.delete('1.0', END)
                text.insert(INSERT, temp)
            
    except Exception as e:
        print(e)

def listbox_copy(e):
    root.clipboard_clear()
    selected = audio_box.get(ACTIVE)
    root.clipboard_append(selected)

def switch_eval(event = None, x = None):
    global eval
    if msv:
        if x != None:
            eval = x
        else:
            eval = not eval 
        eval_button.config(image = mark[eval])
        if not eval:
            temp = 0
        else:
            temp = 1

        json_data['id'][msv][filename].update({
            'accepted': temp
        })
        json_update()

# def move_bad_files():
#     folder_path = filedialog.askdirectory(title = "Select a folder")
#     new_json = {}
#     for sv in json_data['id']:
#         sv_folder_path = folder_path + '/' + sv
 
# Shortcuts
def bind_(widget, all_=False, modifier="", letter="", callback=None, add='',):
    if modifier and letter:
        letter = "-" + letter
    if all_:
        widget.bind_all('<{}{}>'.format(modifier,letter.upper()), callback, add)
        widget.bind_all('<{}{}>'.format(modifier,letter.lower()), callback, add)
    else:
        widget.bind('<{}{}>'.format(modifier,letter.upper()), callback, add)
        widget.bind('<{}{}>'.format(modifier,letter.lower()), callback, add)

bind_(audio_box, modifier="Control", letter = "c", callback = listbox_copy)
bind_(root, modifier="Control", letter="s", callback=save) #Control+s
bind_(root, modifier="Control", letter="p", callback=play) #Control+p
bind_(root, modifier="Control", letter="r", callback=stop) #Control+r
bind_(audio_box, modifier="Control", letter="x", callback=remove_audio) #Control+x
bind_(root, modifier="Control", letter="n", callback=add_audio) #Control+n
bind_(root, modifier="Control", letter="m", callback=add_folder) #Control+m
bind_(root, modifier="Control", letter="q", callback= lambda event: add_point(event, 'Start'))
bind_(root, modifier="Control", letter="w", callback=lambda event: add_point(event, 'End'))
bind_(root, modifier="Control", letter="t", callback=test_test)
bind_(root, modifier="Control", letter="h", callback=speech_to_text)
bind_(root, modifier="Control", letter="e", callback=switch_eval)

root.bind('<Control-space>', pause) #Control+space
root.bind('<Control-0>', increase_volume, '') #Control+0
root.bind('<Control-9>', decrease_volume) #Control+9
root.bind('<Control-[>', slow_down) #Control+Alt+<
root.bind('<Control-]>', speed_up) #Control+Alt+>;
root.bind('<Control-`>', switch_focus) #Control+`
root.bind('<Control-.>', forward) #Control+>
root.bind('<Control-,>', back) #Control+<
root.bind('<Control-j>', left) #Control+;
root.bind('<Control-k>', right) #Control+'
root.bind('<Control-BackSpace>', delete_whole_word)

# Labels
audio_title = tk.Label(root, font=("Calibri",14), fg = '#dcddde', bg ='#36393f', bd=1)
audio_title.grid(row = 1, column = 0, pady = 10, padx = 10)

# Button frame
button_frame = tk.Frame(root, bg = '#36393f')
button_frame.grid(row = 2, column = 0, pady = 10)
# button_frame.grid_columnconfigure((0, 1, 2), weight=1)

back_image = tk.PhotoImage(file = fr"img\back.png")
next_image = tk.PhotoImage(file = fr"img\next.png")
vlov1 = tk.PhotoImage(file = fr"img\vlov01.png")
vlov2 = tk.PhotoImage(file = fr"img\vlov02.png")
paused_image = tk.PhotoImage(file = fr"img\pause.png")
unpausesd_image = tk.PhotoImage(file = fr"img\unpause.png")
stop_image = tk.PhotoImage(file = fr"img\stop.png")
load_text_image = tk.PhotoImage(file = fr"img\text_icon.png")
good = Image.open(fr'img\good.png')
bad = Image.open(fr'img\bad.png')

good = good.resize((30,30))
bad = bad.resize((30,30))
good = ImageTk.PhotoImage(good)
bad = ImageTk.PhotoImage(bad)

mark = [bad, good]

# Buttons
back_button = tk.Button(button_frame, image = back_image, command = back, bg = '#36393f', borderwidth = 0, activebackground="#2f3136")
forward_button = tk.Button(button_frame, image = next_image, command = forward, bg = '#36393f', borderwidth = 0, activebackground="#2f3136")
play_button = tk.Button(button_frame, image = vlov1, command = play, bg = '#36393f', activebackground="#2f3136")
pause_button = tk.Button(button_frame,image = paused_image, command = pause, bg = '#36393f', borderwidth = 0, activebackground="#2f3136")
stop_button = tk.Button(button_frame, image = stop_image, command = stop, bg = '#36393f', borderwidth = 0, activebackground="#2f3136")
load_text_button = tk.Button(button_frame, image = load_text_image, command = speech_to_text, bg = '#36393f', bd = 0, activebackground="#2f3136")

back_button.grid(row = 0, column = 1, padx = 10)
forward_button.grid(row = 0, column = 2, padx = 10)
play_button.grid(row = 0, column = 3, padx = 10)
pause_button.grid(row = 0, column = 4, padx = 10)
stop_button.grid(row = 0, column = 5, padx = 10)
load_text_button.grid(row = 0, column = 0, padx = 10)

# Volume buttons
volume_frame = tk.Frame(button_frame)
volume_frame.grid(row = 0, column = 6, padx = 22)
increase_button = tk.Button(volume_frame, text = "+", font=("Calibri",14), bg = '#36393f', fg = '#dcddde', bd = 1, command = increase_volume, width = 3, activebackground="#2f3136")
decrease_button = tk.Button(volume_frame, text = "-", font=("Calibri",14), bg = '#36393f', fg = '#dcddde', bd = 1, command = decrease_volume, activebackground="#2f3136")

decrease_button.grid(row = 2, column = 0, sticky='ew')
increase_button.grid(row = 0, column = 0, sticky = 'ew')

# Volume label
volume_label = tk.Label(volume_frame, text = json_data['volume'], font=("Calibri",14), fg = '#dcddde', bg = '#292b2f')
volume_label.grid(row = 1, column = 0, sticky = 'ew')

# Slider
slider_bar = tk.Frame(root, bg = '#36393f')
slider_bar.grid(row = 3, column = 0, pady = (0,10), sticky = 'ew')
slider_bar.columnconfigure(0, weight = 1)
slider = ttk.Scale(slider_bar, from_ = 0, to = 100, orient = HORIZONTAL, value = 0, command = slide, style = 'TScale')
slider.grid(row = 1, column = 0, sticky = 'ew', padx = 10)
slider.bind('<Button-1>', set_value)

# Playtime
bar = tk.Label(slider_bar, text = "     ", bd = 1, font=("Calibri",14), bg = '#36393f', fg = '#dcddde')
bar.grid(row = 0, column = 0, pady = 10, sticky = 'ew')

# Save
save_frame = tk.Frame(root, bg = '#36393f', highlightbackground = 'grey', highlightthickness=4)
save_frame.grid(row = 4, column = 0, sticky = 'ew')
save_frame.columnconfigure(1,weight = 1)
save_button = tk.Button(save_frame, text = "Save", font=("Calibri",14), command = save, bd = 0, background = '#36393f', fg = '#dcddde', width = 4, activebackground='#2f3136')
text_path = tk.Text(save_frame, font=("Calibri",14), fg = 'green', height = 1, undo = True, wrap = WORD, bg = '#282a36', bd = 0, insertbackground = 'white')
text_path.config(state = DISABLED)

eval = True
eval_button = tk.Button(save_frame, image = mark[eval], background = '#36393f', bd = 0, activebackground='#2f3136', command = switch_eval)
save_button.grid(row = 0, column = 0, sticky = 'sn')
text_path.grid(row = 0, column = 1, sticky = 'ew')
eval_button.grid(row = 0, column = 2)

# Text
text_frame = tk.Frame(root, bg = '#282a36')
text_frame.grid(row = 5, column = 0, sticky = 'ewsn')
text_frame.rowconfigure(0, weight= 1)
text_frame.columnconfigure(0, weight= 1)
text_frame.columnconfigure(2, weight= 1)
text = tk.Text(text_frame, font=("Calibri",14), undo = True, wrap = WORD, bg = '#28273f', fg = '#dcddde', insertbackground = 'grey', height = 5, width = 10, borderwidth = 5, relief = 'solid')
text.grid(row = 0, column = 0, sticky = 'ewsn')
text_scroll_bar = tk.Scrollbar(text_frame)
text_scroll_bar.grid(row = 0, column = 1, sticky = "sn")
text.configure(yscrollcommand = text_scroll_bar.set)
text_scroll_bar.configure(command = text.yview)

comment_text = tk.Text(text_frame, font=("Calibri",14), undo = True, wrap = WORD, bg = '#44475a', fg = '#dcddde', insertbackground = 'grey', height = 5, width = 10, borderwidth = 5, relief = 'solid')
comment_text.grid(row = 0, column = 2, sticky = 'ewsn')
comment_scroll_bar = tk.Scrollbar(text_frame)
comment_scroll_bar.grid(row = 0, column = 3, sticky = "sn")
comment_text.configure(yscrollcommand = comment_scroll_bar.set)
comment_scroll_bar.configure(command = comment_text.yview)

# Treeview
# tree = new_tree(root)
# tree.grid(row = 0, column = 1, rowspan=5, sticky = "ewsn")

# checkbox_tree = CheckboxTreeview(root, show = 'tree')
# checkbox_tree.grid(row = 0, column = 1, rowspan = 6, sticky = 'ewsn')
# checkbox_tree.insert('', 'end', 'b19dcdt093', tags = 'checked', text = 'B19DCDT093')

# Menu
menu = tk.Menu(root, bg = 'red')
root.config(menu = menu)

# Add audio files menu
file_menu = tk.Menu(menu)
menu.add_cascade(label = "File", menu = file_menu)
file_menu.add_command(label = "Add files", command = add_audio, accelerator="Ctrl+N")
file_menu.add_command(label = "Add folder", command = add_folder, accelerator="Ctrl+M")
file_menu.add_command(label = "Save", command = save, accelerator="Ctrl+S")
# file_menu.add_command(label = "Move bad files", command = move_bad_files)


# # Delete audio files menu
# delete_audio_menu = tk.Menu(menu)
# menu.add_cascade(label = "Remove", menu = delete_audio_menu)
# delete_audio_menu.add_command(label = "Remove files from box", command = remove_audio, accelerator="Ctrl+X")

# Export menu
export_menu = tk.Menu(menu)
menu.add_cascade(label = "Export", menu = export_menu)
export_menu.add_command(label = "Export all segments", command = export_segments)

# Tools
tools_menu = tk.Menu(menu)
menu.add_cascade(label = "Tools", menu = tools_menu)
transcript_mode = tk.BooleanVar(value = True)
tools_menu.add_checkbutton(label = "Transcript", command = toggle_transcript, variable = transcript_mode, onvalue=1, offvalue=0)
tools_menu.add_command(label = "Convert audio to text", command = speech_to_text, accelerator="Ctrl+H")

root.update()
root.minsize(root.winfo_width(), root.winfo_height())

for i, v in enumerate(json_data['audio_paths']):
    audio_box.insert(END, v)
    marked[v] = i
audio_box.focus()
audio_box.selection_clear(0, END)
audio_box.selection_set(END)
audio_box.see(END)
audio_box.activate(END)

root.mainloop()
