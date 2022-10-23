
import tkinter as tk
from tkinter.constants import ACTIVE, END, EXTENDED, HORIZONTAL, INSERT, WORD
from tkinter import ANCHOR, DISABLED, NORMAL, W, filedialog
import tkinter.ttk as ttk
import subprocess
import os 
import json
import vlc
import speech_recognition as sr

def bind_(widget, all_=False, modifier="", letter="", callback=None, add='',):
    if modifier and letter:
        letter = "-" + letter
    if all_:
        widget.bind_all('<{}{}>'.format(modifier,letter.upper()), callback, add)
        widget.bind_all('<{}{}>'.format(modifier,letter.lower()), callback, add)
    else:
        widget.bind('<{}{}>'.format(modifier,letter.upper()), callback, add)
        widget.bind('<{}{}>'.format(modifier,letter.lower()), callback, add)

def get_duration(file):
    p = subprocess.Popen(r'bin\ffprobe -i "{}" -show_entries format=duration'.format(file),stdout=subprocess.PIPE,stderr = subprocess.PIPE,universal_newlines=True)
    duration = float(p.stdout.readlines()[1].replace('duration=', ''))
    return duration

def sec2mmss(sec, round = True):
    minutes = 0
    seconds = 0
    minutes = sec//60
    seconds = sec - minutes*60
    if round:
        return '{:02.0f}:{:02}'.format(minutes, int(seconds))
    else:
        return '{:02.0f}:{:06.3f}'.format(int(minutes), seconds)

class window(tk.Tk):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.resizable(True, True)
        self.rate = 1
        self.title('GUI x' + str(self.rate))
        self.config(bg = '#36393f')
        self.call('wm', 'iconphoto', self._w, tk.PhotoImage(file = fr"img\MBTL_faq_icon.png"))
        self.rowconfigure(2, weight = 1)
        self.columnconfigure(0, weight = 1)
        self.style = ttk.Style()
        if self.getvar('tk_patchLevel')=='8.6.9': #and OS_Name=='nt':
            def fixed_map(option):
                return [elm for elm in self.style.map('Treeview', query_opt=option) if elm[:2] != ('!disabled', '!selected')]
            self.style.map('Treeview', foreground=fixed_map('foreground'), background=fixed_map('background'), fieldbackground=fixed_map('fieldbackground'))
            self.style.map('TScale', foreground=fixed_map('foreground'), background=fixed_map('background'), fieldbackground=fixed_map('fieldbackground'))
        self.style.configure("TScale", background = '#36393f', foreground = 'red', fieldbackground = 'red')
        self.style.configure("Treeview", background="#2f3136", foreground="#dcddde", fieldbackground="red", font = ('',11))
        self.style.map("Treeview", foreground = [])
        
        # Player
        self.player = Player(self, state_path = 'bin/state.json')
        self.player.grid(row = 1, column = 0, sticky = 'ew')

        # Transcript box
        self.transcript_box = Transcript_Box(self)
        self.transcript_box.grid(row = 2, column = 0, sticky = 'ewsn')

        # Tree table
        self.tree_table = Tree_Table(self)
        self.tree_table.grid(row = 0, column = 1, sticky = 'sn', rowspan = 5)

        # Shortkeys
        
        # bind_(self, modifier = 'Control', letter = 'x', callback = self.remove_files)
        # self.bind('<Control-[>', decrease_volume)

class Player(tk.Frame):
    def __init__(self, *args, **kwargs):
        super().__init__(*args)
        self.state_path = kwargs['state_path']
        with open(self.state_path, 'r', encoding = 'utf-8') as file:
            self.state = json.loads(file.read())

        self.root = args[0]
        self.loop = None
        self.config(bg = '#36393f')
        self.marked = {}
        self.active_file = ''
        self.current_time = 0
        self.total_duration = 0
        self.columnconfigure(0, weight = 1)

        instance = vlc.Instance()
        instance.log_unset()
        self.vlc_player = instance.media_player_new()
        self.vlc_player.audio_set_volume(self.state['volume'])

        # List box
        self.listbox_frame = tk.Frame(self)
        self.listbox_frame.columnconfigure(0, weight = 1)
        self.listbox_frame.grid(row = 0, column = 0, sticky = 'eswn')
        self.listbox = tk.Listbox(self.listbox_frame, bg = '#282a36', fg="green", selectbackground="grey", selectmode=EXTENDED, exportselection=False, font=("Calibri",12))
        self.listbox.grid(row = 0, column = 0, sticky = 'eswn')
        self.scrollbar = tk.Scrollbar(self.listbox_frame)
        self.scrollbar.grid(row = 0, column = 1, sticky = 'sn')
        self.listbox.configure(yscrollcommand = self.scrollbar.set)
        self.scrollbar.configure(command = self.listbox.yview)

        # Title
        self.audio_title = tk.Label(self, font=("Calibri",14), fg = '#dcddde', bg ='#36393f', bd=1)
        self.audio_title.grid(row = 1, column = 0, pady = 10, padx = 10)

        # Button images
        self.back_image = tk.PhotoImage(file = fr"img\back.png")
        self.next_image = tk.PhotoImage(file = fr"img\next.png")
        self.vlov1 = tk.PhotoImage(file = fr"img\vlov01.png")
        self.vlov2 = tk.PhotoImage(file = fr"img\vlov02.png")
        self.paused_image = tk.PhotoImage(file = fr"img\pause.png")
        self.unpausesd_image = tk.PhotoImage(file = fr"img\unpause.png")
        self.stop_image = tk.PhotoImage(file = fr"img\stop.png")
        self.load_text_image = tk.PhotoImage(file = fr"img\text_icon.png")

        # Buttons
        self.button_frame = tk.Frame(self, bg = '#36393f')
        self.speech_to_text_button = tk.Button(self.button_frame, image = self.load_text_image, bg = '#36393f', bd = 0, activebackground="#2f3136")
        self.back_button = tk.Button(self.button_frame, image = self.back_image, bg = '#36393f', borderwidth = 0, activebackground="#2f3136", command = lambda: self.next_file(add =  -1))
        self.forward_button = tk.Button(self.button_frame, image = self.next_image, bg = '#36393f', borderwidth = 0, activebackground="#2f3136", command = lambda: self.next_file(add =  1))
        self.play_button = tk.Button(self.button_frame, image = self.vlov1, bg = '#36393f', activebackground="#2f3136", command = self.play)
        self.pause_button = tk.Button(self.button_frame,image = self.paused_image, bg = '#36393f', borderwidth = 0, activebackground="#2f3136", command = self.pause)
        self.stop_button = tk.Button(self.button_frame, image = self.stop_image, bg = '#36393f', borderwidth = 0, activebackground="#2f3136")
        self.volume_buttons = tk.Frame(self.button_frame, bg = '#36393f')
        self.increase_button = tk.Button(self.volume_buttons, text = "+", font=("Calibri",14), bg = '#36393f', fg = '#dcddde', bd = 1, width = 3, activebackground="#2f3136", command = lambda: self.volume_update(value = 2))
        self.decrease_button = tk.Button(self.volume_buttons, text = "-", font=("Calibri",14), bg = '#36393f', fg = '#dcddde', bd = 1, activebackground="#2f3136", command = lambda: self.volume_update(value = -2))
        self.volume_label = tk.Label(self.volume_buttons, font=("Calibri",14), fg = '#dcddde', bg = '#292b2f', text = self.state['volume'])

        # Button positions
        self.button_frame.grid(row = 2, column = 0, pady = 10)
        self.speech_to_text_button.grid(row = 0, column = 0, padx = 10)
        self.back_button.grid(row = 0, column = 1, padx = 10)
        self.forward_button.grid(row = 0, column = 2, padx = 10)
        self.play_button.grid(row = 0, column = 3, padx = 10)
        self.pause_button.grid(row = 0, column = 4, padx = 10)
        self.stop_button.grid(row = 0, column = 5, padx = 10)
        self.volume_buttons.grid(row = 0, column = 6, padx = 22)
        self.decrease_button.grid(row = 2, column = 0, sticky='ew')
        self.increase_button.grid(row = 0, column = 0, sticky = 'ew')
        self.volume_label.grid(row = 1, column = 0, sticky = 'ew')

        # Timestamps
        self.timestamp = tk.Label(self, text = '', bd = 1, font=("Calibri",14), bg = '#36393f', fg = '#dcddde')
        self.timestamp.grid(row = 3, column = 0)
        
        # Slider
        self.slider = ttk.Scale(self, from_ = 0, to = 100, orient = HORIZONTAL, value = 0, command = self.slide, style = 'TScale')
        self.slider.grid(row = 4, column = 0, sticky = 'ew', pady = (0,10), padx = 10)
        self.slider.bind('<Button-1>', self.set_value)

        # Shortkeys
        bind_(self.root, modifier = 'Control', letter = 'n', callback = self.add_files)
        bind_(self.root, modifier = 'Control', letter = 'm', callback = self.add_folder)
        bind_(self.listbox, modifier = 'Control', letter = 'x', callback = self.remove_files)

        bind_(self.root, modifier = 'Control', letter = 'p', callback = self.play)
        self.listbox.bind('<Double-Button-1>', self.play)
        self.root.bind('<Control-space>', self.pause)
        bind_(self.root, modifier = 'Control', letter = 'j', callback = lambda key: self.seek(key, add = -2))
        bind_(self.root, modifier = 'Control', letter = 'k', callback = lambda key: self.seek(key, add = 2))
        self.root.bind('<Control-,>', lambda x: self.next_file(x, add = -1))
        self.root.bind('<Control-.>', lambda x: self.next_file(x, add = 1))

        self.root.bind('<Control-9>', lambda x: self.volume_update(x, -2))
        self.root.bind('<Control-0>', lambda x: self.volume_update(x, 2))

        self.update(self.state['audio_paths'], begin  = True)

    def state_file_update(self):
        with open(self.state_path, 'w', encoding = 'utf-8') as file:
            json.dump(self.state, file, ensure_ascii = False, indent = 4)

    def listbox_focus_on(self, index):
        self.listbox.selection_clear(0, END)
        self.listbox.selection_set(index)
        self.listbox.see(index)
        self.listbox.activate(index)

    def update(self, l, begin = False):
        self.listbox.focus()
        for file_path in l:
            if file_path in self.marked:
                self.listbox_focus_on(self.marked[file_path])
                continue
            print(len(self.state['audio_paths']))
            self.marked[file_path] = len(self.marked)
            if not begin:
                self.state['audio_paths'].append(file_path)
            self.state_file_update()
            self.listbox.insert(END, file_path)
            self.listbox_focus_on(END)
    
    def add_files(self, event = None):
        file_paths = filedialog.askopenfilenames(title = "Select audio files", filetypes=[("mp3 files","*.mp3"), ("wav files","*.wav"), ("all files","*.*")])
        self.update(file_paths)

    def add_folder(self, event = None):
        folder_path = filedialog.askdirectory(title = "Select a folder")
        file_paths = []
        for roots, subdirs, files in os.walk(folder_path):
            for file in files:
                if file.endswith(('.mp3', '.wav', '.ogg', '.webm')):
                    file_paths.append(f'{roots}/{file}')
        self.update(file_paths)

    def remove_files(self, event = None):
        try:
            selection = self.listbox.curselection()
            next = selection[0]
            for i in reversed(selection):
                if self.listbox.get(i) == self.active_file:
                    self.root.transcript_box.clear()
                    self.root.tree_table.clear()
                    self.clear()
                    self.vlc_player.stop()
                self.listbox.delete(i)
                del self.marked[self.state['audio_paths'][i]]
                del self.state['audio_paths'][i]
            self.state_file_update()
            if next == self.listbox.size():
                next -= 1
            self.listbox.selection_set(next)
        except Exception as e:
            print(e)
            pass

    def play(self, event = None):
        self.reset()
        self.play_button['image'] = self.vlov2
        file_path = self.listbox.get(ACTIVE)
        if self.active_file != file_path:
            self.active_file = file_path
            self.audio_title.config(text = os.path.basename(file_path))
            self.root.transcript_box.load_text()
            self.root.tree_table.load_segments()
        self.vlc_player.set_media(vlc.Media(file_path))
        self.total_duration = get_duration(file_path)
        self.slider.config(from_ = 0, to = self.total_duration, value = 0)
        self.pause_button['image'] = self.unpausesd_image
        self.vlc_player.play()
        self.play_time()
        self.play_button.after(500, lambda: self.play_button.config(image = self.vlov1))

    def pause(self, event = None):
        if self.vlc_player.get_state() == vlc.State.Playing:
            self.vlc_player.pause()
            self.pause_button['image'] = self.paused_image
            if self.loop is not None:
                self.after_cancel(self.loop)
        else:
            self.vlc_player.play()
            self.play_time()
            self.pause_button['image'] = self.unpausesd_image

    def reset(self, event = None):
        self.vlc_player.stop()
        if self.loop is not None:
            self.after_cancel(self.loop)

    def clear(self, event = None):
        self.audio_title.config(text = '')
        self.timestamp.config(text = '00:00/00:00')
        self.active_file = ''
        self.slider.config(value = 0)

    def play_time(self):
        self.current_time = self.vlc_player.get_time() / 1000
        if self.vlc_player.get_state() == 6:
            self.slider.config(value = self.total_duration)
            self.timestamp.config(text = "{}/{}".format(sec2mmss(self.total_duration), sec2mmss(self.total_duration)))
            self.play()
        # elif tree.seg_play and current_time >= tree.pause_point:
        #     pause()
        #     slider.config(value = tree.pause_point)
        #     player.set_position(tree.pause_point/total_duration)
        #     tree.seg_play = False
        else:
            self.timestamp.config(text = "{}/{}".format(sec2mmss(self.current_time), sec2mmss(self.total_duration)))
            self.slider.config(value = self.current_time)
        self.loop = self.after(50, self.play_time)
    
    def next_file(self, event = None, add = 1):
        try:
            next = self.listbox.curselection()[0] + add
            if next >= self.listbox.size():
                next = 0
            elif next < 0:
                next = self.listbox.size() - 1
            self.listbox.selection_clear(0, END)
            self.listbox.activate(next)
            self.listbox.selection_set(next)
            self.listbox.see(next)
            self.play()
        except Exception as e:
            pass

    def volume_update(self, event = None, value = 2):
        temp = self.state['volume'] + value
        if temp >= 0 and temp <= 100:
            self.state['volume'] += value
            self.volume_label.config(text = str(temp))
            self.vlc_player.audio_set_volume(temp)
            self.state_file_update()

    def set_value(self, event):
        self.slider.event_generate('<Button-3>', x=event.x, y=event.y)
        return 'break'
    
    def slide(self, event = None):
        slider_pos = self.slider.get()
        if self.loop is not None:
            self.after_cancel(self.loop)
        self.vlc_player.set_position(slider_pos/self.total_duration)
        # tree.seg_play = False
        self.play_time()

    def seek(self, event = None, add = 2):
        slider_pos = self.slider.get() + add
        self.slider.config(value = slider_pos)
        if self.loop is not None:
            self.after_cancel(self.loop)
        self.vlc_player.set_position(slider_pos/self.total_duration)
        # tree.seg_play = False
        self.play_time()
    
class Transcript_Box(tk.Frame):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.root = args[0]
        self.config(bg = 'red')
        self.txt_path = ''
        self.columnconfigure(0, weight = 1)
        self.rowconfigure(1, weight = 1)

        # Save button and text path
        self.row1 = tk.Frame(self, bg = '#36393f', highlightbackground = 'grey', highlightthickness=4)
        self.row1.grid(row = 0, column = 0, sticky = 'ew')
        self.row1.columnconfigure(1, weight = 1)

        self.save_button = tk.Button(self.row1, text = "Save", font=("Calibri",14), bd = 0, background = '#36393f', fg = '#dcddde', width = 4, activebackground='#2f3136')
        self.save_button.grid(row = 0, column = 0, sticky = 'ew')
        self.text_path = tk.Text(self.row1, font=("Calibri",14), fg = 'green', height = 1, undo = True, wrap = WORD, bg = '#282a36', bd = 0, insertbackground = 'white')
        self.text_path.grid(row = 0, column = 1, sticky = 'ew')
        self.text_path.config(state = DISABLED)

        # Text box
        self.row2 = tk.Frame(self)
        self.row2.grid(row = 1, column = 0, sticky = 'ewsn')
        self.row2.columnconfigure(0, weight = 1)
        self.row2.rowconfigure(0, weight = 1)

        self.text_box = tk.Text(self.row2, font=("Calibri",14), undo = True, wrap = WORD, bg = '#282a36', fg = '#dcddde', insertbackground = 'grey', height = 5)
        self.text_box.grid(row = 0, column = 0, sticky = 'ewsn')
        self.scrollbar = tk.Scrollbar(self.row2)
        self.scrollbar.grid(row = 0, column = 1, sticky = 'sn')
        self.text_box.configure(yscrollcommand = self.scrollbar.set)
        self.scrollbar.configure(command = self.text_box.yview)

        # bind_(self.root, modifier = 'Control', letter= 's', self.save)
        self.text_box.bind('<Control-BackSpace>', self.delete_whole_word)
        bind_(self.root, modifier = 'Control', letter = 's', callback = self.save)

    def clear(self):
        self.text_path.config(state = NORMAL)
        self.text_path.delete('1.0', END)
        self.text_box.delete('1.0', END)
        self.text_path.config(state = DISABLED)
        self.txt_path = ''

    def save(self, event = None):
        self.save_button.config(text = '......')
        t = self.text_box.get('1.0', END)[:-1]
        with open(self.txt_path, 'w', encoding = 'utf-8') as file:
            file.write(t)
        self.after(500, lambda: self.save_button.config(text = 'Save'))

    def load_text(self):
        file_path = os.path.splitext(self.root.player.active_file)[0] + '.txt'
        self.text_box.delete('1.0', END)
        self.txt_path = file_path
        self.text_path.config(state = NORMAL)
        self.text_path.delete('1.0', END)
        self.text_path.insert(INSERT, file_path)
        self.text_path.config(state = DISABLED)
        if os.path.isfile(file_path):
            with open(file_path, 'r', encoding = 'utf-8') as file:
                t = file.read()
            self.text_box.insert(INSERT, t)

    def delete_whole_word(self, event):
        self.text_box.delete("insert-1c wordstart", "insert")
        return "break"

class Tree_Table(tk.Frame):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.root = args[0]
        self.id_count = 0
        self.segments_path = ''
        self.segments = {}
        self.if_overlap = {}
        self.playback = False
        self.rowconfigure(0, weight = 1)

        # Treeview
        self.treeview = ttk.Treeview(self)
        self.treeview.grid(row = 0, column = 0, sticky = 'sn')
        self.scrollbar = tk.Scrollbar(self)
        self.scrollbar.grid(row = 0, column = 1, sticky = 'sn')
        self.treeview.configure(yscrollcommand = self.scrollbar.set)
        self.scrollbar.configure(command = self.treeview.yview)

        self.treeview.tag_configure('highlight', foreground = 'white')
        self.treeview.tag_configure('overlap', foreground = '#CA0B00')

        self.treeview['columns'] = ("Start", "End")
        self.treeview.column("#0", width = 1, anchor = W)
        self.treeview.column("Start", width = 100, anchor = W)
        self.treeview.column("End", width = 100, anchor = W)

        self.treeview.heading("Start", text = "Start", anchor = W)
        self.treeview.heading("End", text = "End", anchor = W)

        # Shortkeys
        bind_(self.root, modifier = 'Control', letter = 't', callback = self.new_segment)
        bind_(self.treeview, modifier = 'Control', letter = 'x', callback = self.delete_segments)
        bind_(self.root, modifier = 'Control', letter = 'q', callback = lambda event: self.modify_segment(event, col = 'Start'))
        bind_(self.root, modifier = 'Control', letter = 'w', callback = lambda event: self.modify_segment(event, col = 'End'))
        self.treeview.bind('<Double-Button-1>', self.jump)

    def new_segment(self, event = None):
        t = self.root.player.current_time
        self.segments[self.id_count] = {
            'Start': t,
            'End': self.root.player.total_duration
        }
        self.treeview.insert('', END, iid = self.id_count, values=[sec2mmss(self.segments[self.id_count]['Start'], False), sec2mmss(self.segments[self.id_count]['End'], False)])
        self.treeview.selection_set(self.id_count)
        self.treeview.focus(self.id_count)
        self.id_count += 1
        self.segments_file_update()
        self.check_overlap()

    def modify_segment(self, event = None, col = 'Start'):
        t = self.root.player.current_time
        iid = self.treeview.selection()[0]
        self.segments[int(iid)][col] = t
        self.treeview.set(iid, col, sec2mmss(t, False))
        self.check_overlap()
    
    def jump(self, event):
        row = int(self.treeview.identify_row(event.y))
        col = int(self.treeview.identify_column(event.x)[1:])
        if col == 2:
            slider_pos = self.segments[row]['End']
            self.playback = False
        else:
            self.playback = True
            self.pause_point = self.segments[row]['End']
            slider_pos = self.segments[row]['Start']
        self.root.player.slider.config(value = slider_pos)
        if self.root.player.loop is not None:
            self.root.player.after_cancel(self.root.player.loop)
        self.root.player.vlc_player.set_position(slider_pos/self.root.player.total_duration)
        self.root.player.play_time()

    def segments_file_update(self):
        with open(self.segments_path, 'w', encoding = 'utf-8') as file:
            json.dump(self.segments, file, ensure_ascii = False, indent = 4)

    def load_segments(self):
        self.root.tree_table.clear()
        file_path = os.path.splitext(self.root.player.active_file)[0] + '.json'
        self.segments_path = file_path
        if os.path.isfile(file_path):
            try:
                with open(file_path, 'r', encoding = 'utf-8') as file:
                    self.segments = json.loads(file.read(), object_hook=lambda d: {int(k) if k.lstrip('-').isdigit() else k: v for k, v in d.items()})
                for i, v in self.segments.items():
                    self.treeview.insert('', END, iid = i, values = [sec2mmss(v['Start'], False), sec2mmss(v['End'], False)])

                self.id_count = list(self.segments)[-1]
                self.treeview.selection_set(self.id_count)
                self.treeview.focus(self.id_count)
                self.id_count += 1
                self.check_overlap()
            except Exception as e:
                pass
            print(self.id_count)

    def delete_segments(self, event = None):
        try:
            for row in self.treeview.selection():
                self.treeview.delete(row)
                del self.segments[int(row)]
            self.check_overlap()
            self.segments_file_update()
        except Exception as e:
            print(e)
            pass
    
    def clear(self):
        self.treeview.delete(*self.treeview.get_children())
        self.id_count = 0
        self.segments_path = ''
        self.segments = {}
        self.if_overlap = {}
        self.playback = False

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