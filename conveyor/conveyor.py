#!/usr/bin/env python

'''
Odor presentation

Creates GUI to control behavioral and imaging devices for in vivo calcium
imaging. Script interfaces with Arduino microcontroller and imaging devices.
'''
import sys
is_py2 = sys.version[0] == '2'

import matplotlib
matplotlib.use('TKAgg')
if is_py2:
    import Tkinter as tk
    import ttk
    import tkFont
    import tkMessageBox
    import tkFileDialog
    from ScrolledText import ScrolledText
    from Queue import Queue
else:
    import tkinter as tk
    import tkinter.ttk as ttk
    import tkinter.font as tkFont
    import tkinter.messagebox as tkMessageBox
    import tkinter.filedialog as tkFileDialog
    from tkinter.scrolledtext import ScrolledText
    from queue import Queue
from PIL import ImageTk
import collections
import serial
import serial.tools.list_ports
import threading
from slackclient import SlackClient
import time
from datetime import datetime
from datetime import timedelta
import os
import sys
import h5py
import numpy as np
from matplotlib.figure import Figure
import matplotlib.animation as animation
from matplotlib.colors import LinearSegmentedColormap
from matplotlib import style
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2TkAgg
import seaborn as sns

import pdb


# Setup Slack
try:
    slack_token = os.environ['SLACK_API_TOKEN']
except KeyError:
    print('Environment variable SLACK_API_TOKEN not identified')
    slack = None
else:
    slack = SlackClient(slack_token)

# Header to print with Arduino outputs
arduino_head = '  [a]: '

entry_width = 10
ew = 10  # Width of Entry UI
px = 15
py = 5
px1 = 5
py1 = 2

# Serial codes
code_end = 0
code_steps = 1
code_trial_start = 3
code_trial_man = 4
code_rail_leave = 5
code_rail_home = 6
code_track = 7


class InputManager(tk.Frame):

    def __init__(self, parent):
        tk.Frame.__init__(self, parent)

        # GUI layout
        # parent
        # - frame_setup
        #   + frame_params
        #     ~ frame_session
        #     ~ frame_misc
        #   + hardware_frame
        #     ~ frame_preview
        #     ~ frame_arduino
        #     ~ frame_debug
        #   + frame_file
        #   + slack_frame
        # - monitor_frame
        #   + (figure)
        #   + scoreboard_frame

        self.parent = parent
        parent.columnconfigure(0, weight=1)

        self.var_port = tk.StringVar()
        self.var_image_all = tk.BooleanVar()
        self.var_verbose = tk.BooleanVar()
        self.var_print_arduino = tk.BooleanVar()
        self.var_stop = tk.BooleanVar()

        # Lay out GUI

        frame_setup = tk.Frame(parent)
        frame_setup.grid(row=0, column=0)
        frame_setup_col0 = tk.Frame(frame_setup)
        frame_setup_col1 = tk.Frame(frame_setup)
        frame_setup_col2 = tk.Frame(frame_setup)
        frame_setup_col0.grid(row=0, column=0, sticky='we')
        frame_setup_col1.grid(row=0, column=1, sticky='we')
        frame_setup_col2.grid(row=0, column=2, sticky='we')

        # Session frame
        frame_params = tk.Frame(frame_setup_col0)
        frame_params.grid(row=0, column=0, padx=15, pady=5)
        frame_params.columnconfigure(0, weight=1)

        frame_session = tk.Frame(frame_params)
        frame_misc = tk.Frame(frame_params)
        frame_session.grid(row=0, column=0, sticky='e', padx=px, pady=py)
        frame_misc.grid(row=2, column=0, sticky='e', padx=px, pady=py)
 
        # Arduino frame
        frame_arduino = ttk.LabelFrame(frame_setup_col1, text='Arduino')
        frame_arduino.grid(row=1, column=0, padx=px, pady=py, sticky='we')
        frame_arduino1 = tk.Frame(frame_arduino)
        frame_arduino2 = tk.Frame(frame_arduino)
        frame_arduino1.grid(row=0, column=0, sticky='we', padx=px, pady=py)
        frame_arduino2.grid(row=1, column=0, sticky='we', padx=px, pady=py)
        frame_arduino2.grid_columnconfigure(0, weight=1)
        frame_arduino2.grid_columnconfigure(1, weight=1)
        frame_arduino.grid_columnconfigure(0, weight=1)
        
        # Debug frame
        frame_debug = ttk.LabelFrame(frame_setup_col1, text='Debug')
        frame_debug.grid(row=2, column=0, padx=px, pady=py, sticky='we')
        frame_debug.grid_columnconfigure(0, weight=1)

        # Notes frame
        frame_notes = tk.Frame(frame_setup_col2)
        frame_notes.grid(row=0, sticky='wens', padx=px, pady=py)
        frame_notes.grid_columnconfigure(0, weight=1)

        # Saved file frame
        frame_file = tk.Frame(frame_setup_col2)
        frame_file.grid(row=1, column=0, padx=px, pady=py, sticky='we')
        frame_file.columnconfigure(0, weight=3)
        frame_file.columnconfigure(1, weight=1)

        # Slack frame
        frame_slack = tk.Frame(frame_setup_col2)
        frame_slack.grid(row=2, column=0, sticky='we', padx=px, pady=py)
        frame_slack.grid_columnconfigure(0, weight=3)
        frame_slack.grid_columnconfigure(1, weight=1)

        # Start-stop frame
        frame_start = tk.Frame(frame_setup_col2)
        frame_start.grid(row=3, column=0, sticky='we', padx=px, pady=py)
        frame_start.grid_columnconfigure(0, weight=1)
        frame_start.grid_columnconfigure(1, weight=1)

        # Add GUI components

        ## frame_params

        ### frame_session
        ## UI for trial control
        self.entry_pre_session = ttk.Entry(frame_session, width=entry_width)
        self.entry_post_session = ttk.Entry(frame_session, width=entry_width)
        self.entry_trial_num = ttk.Entry(frame_session, width=entry_width)
        self.entry_trial_dur = ttk.Entry(frame_session, width=entry_width)
        self.entry_iti = ttk.Entry(frame_session, width=entry_width)
        tk.Label(frame_session, text='Presession time (ms): ', anchor='e').grid(row=0, column=0, sticky='e')
        tk.Label(frame_session, text='Postsession time (ms): ', anchor='e').grid(row=1, column=0, sticky='e')
        tk.Label(frame_session, text='Number of trials: ', anchor='e').grid(row=2, column=0, sticky='e')
        tk.Label(frame_session, text='Trial duration (ms): ', anchor='e').grid(row=3, column=0, sticky='e')
        tk.Label(frame_session, text='ITI (ms): ', anchor='e').grid(row=4, column=0, sticky='e')
        self.entry_pre_session.grid(row=0, column=1, sticky='w')
        self.entry_post_session.grid(row=1, column=1, sticky='w')
        self.entry_trial_num.grid(row=2, column=1, sticky='w')
        self.entry_trial_dur.grid(row=3, column=1, sticky='w')
        self.entry_iti.grid(row=4, column=1, sticky='w')

        ### frame_misc
        ### UI for miscellaneous parameters
        self.check_image_all = ttk.Checkbutton(frame_misc, variable=self.var_image_all)
        self.entry_image_ttl_dur = ttk.Entry(frame_misc, width=entry_width)
        self.entry_track_period = ttk.Entry(frame_misc, width=entry_width)
        self.entry_track_steps = ttk.Entry(frame_misc, width=entry_width)
        tk.Label(frame_misc, text='Image everything: ', anchor='e').grid(row=0, column=0, sticky='e')
        tk.Label(frame_misc, text='Imaging TTL duration (ms): ', anchor='e').grid(row=1, column=0, sticky='e')
        tk.Label(frame_misc, text='Track period (ms): ', anchor='e').grid(row=2, column=0, sticky='e')
        tk.Label(frame_misc, text='Track steps: ', anchor='e').grid(row=3, column=0, sticky='e')
        self.check_image_all.grid(row=0, column=1, sticky='w')
        self.entry_image_ttl_dur.grid(row=1, column=1, sticky='w')
        self.entry_track_period.grid(row=2, column=1, sticky='w')
        self.entry_track_steps.grid(row=3, column=1, sticky='w')

        ### frame_arduino
        ### UI for Arduino
        self.option_ports = ttk.OptionMenu(frame_arduino1, self.var_port, [])
        self.button_update_ports = ttk.Button(frame_arduino1, text='u', command=self.update_ports)
        self.entry_serial_status = ttk.Entry(frame_arduino1)
        self.button_open_port = ttk.Button(frame_arduino2, text='Open', command=self.open_serial)
        self.button_close_port = ttk.Button(frame_arduino2, text='Close', command=self.close_serial)
        tk.Label(frame_arduino1, text='Port: ').grid(row=0, column=0, sticky='e')
        tk.Label(frame_arduino1, text='State: ').grid(row=1, column=0, sticky='e')
        self.option_ports.grid(row=0, column=1, sticky='we', padx=5)
        self.button_update_ports.grid(row=0, column=2, pady=py)
        self.entry_serial_status.grid(row=1, column=1, columnspan=2, sticky='w', padx=px1)
        self.button_open_port.grid(row=0, column=0, pady=py, sticky='we')
        self.button_close_port.grid(row=0, column=1, pady=py, sticky='we')

        icon_refresh = ImageTk.PhotoImage(file='graphics/refresh.png')
        self.button_update_ports.config(image=icon_refresh)
        self.button_update_ports.image = icon_refresh

        ## UI for debug options
        self.check_verbose = ttk.Checkbutton(frame_debug, text=' Verbose', variable=self.var_verbose)
        self.check_print = ttk.Checkbutton(frame_debug, text=' Print Arduino output', variable=self.var_print_arduino)
        self.check_verbose.grid(row=0, column=0, padx=px1, sticky='w')
        self.check_print.grid(row=1, column=0, padx=px1, sticky='w') 

        ## Notes
        tk.Label(frame_notes, text='Notes:').grid(row=0, column=0, sticky='w')
        self.scrolled_notes = ScrolledText(frame_notes, width=20, height=15)
        self.scrolled_notes.grid(row=1, column=0, sticky='wens')

        ## UI for saved file
        self.entry_save = ttk.Entry(frame_file)
        self.button_save_file = ttk.Button(frame_file, command=self.get_save_file)
        tk.Label(frame_file, text='File to save data:', anchor='w').grid(row=0, column=0, columnspan=2, sticky='w')
        self.entry_save.grid(row=1, column=0, sticky='wens')
        self.button_save_file.grid(row=1, column=1, sticky='e')

        icon_folder = ImageTk.PhotoImage(file='graphics/folder.png')
        self.button_save_file.config(image=icon_folder)
        self.button_save_file.image = icon_folder
        
        
        ## Slack
        tk.Label(frame_slack, text='Slack address: ', anchor='w').grid(row=0, column=0, sticky='we')
        self.entry_slack = ttk.Entry(frame_slack)
        self.button_slack = ttk.Button(frame_slack, command=lambda: slack_msg(self.entry_slack.get(), 'Test', test=True))
        self.entry_slack.grid(row=1, column=0, sticky='wens')
        self.button_slack.grid(row=1, column=1, sticky='e')

        icon_slack = ImageTk.PhotoImage(file='graphics/slack.png')
        self.button_slack.config(image=icon_slack)
        self.button_slack.image = icon_slack

        ## Start frame
        self.button_start = ttk.Button(frame_start, text='Start', command=lambda: self.parent.after(0, self.start))
        self.button_stop = ttk.Button(frame_start, text='Stop', command=lambda: self.var_stop.set(True))
        self.button_start.grid(row=2, column=0, sticky='we')
        self.button_stop.grid(row=2, column=1, sticky='we')
        
        ###### GUI OBJECTS ORGANIZED BY TIME ACTIVE ######
        # List of components to disable at open
        self.obj_to_disable_at_open = [
            self.option_ports,
            self.button_update_ports,
            self.button_open_port,
            self.entry_pre_session,
            self.entry_post_session,
            self.entry_trial_num,
            self.entry_trial_dur,
            self.entry_track_period,
            self.entry_track_steps,
            self.check_print
        ]
        # Boolean of objects in list above that should be enabled when time...
        self.obj_enabled_at_open = [False] * len(self.obj_to_disable_at_open)
        
        self.obj_to_enable_at_open = [
            self.button_close_port,
            self.button_start
        ]
        self.obj_to_disable_at_start = [
            self.button_close_port,
            self.entry_save,
            self.button_save_file,
            self.button_start,
            self.button_slack
        ]
        self.obj_to_enable_at_start = [
            self.button_stop
        ]

        # Update
        self.update_ports()

        # Default values
        self.entry_pre_session.insert(0, 30000)
        self.entry_post_session.insert(0, 30000)
        self.entry_trial_num.insert(0, 15)
        self.entry_trial_dur.insert(0, 10000)
        self.entry_iti.insert(0, 60000)
        self.entry_image_ttl_dur.insert(0, 100)
        self.entry_track_period.insert(0, 50)
        self.entry_track_steps.insert(0, 5)
        self.entry_serial_status.insert(0, 'Closed')
        self.entry_serial_status['state'] = 'normal'
        self.entry_serial_status['state'] = 'readonly'
        self.button_close_port['state'] = 'disabled'
        self.button_start['state'] = 'disabled'
        self.button_stop['state'] = 'disabled'

        ###### SESSION VARIABLES ######
        self.parameters = collections.OrderedDict()
        self.ser = serial.Serial(timeout=1, baudrate=9600)
        self.counter = {}
        self.q = Queue()
        self.gui_update_ct = 0  # count number of times GUI has been updated

    def update_ports(self):
        ports_info = list(serial.tools.list_ports.comports())
        ports = [port.device for port in ports_info]
        ports_description = [port.description for port in ports_info]

        menu = self.option_ports['menu']
        menu.delete(0, 'end')
        if ports:
            for port, description in zip(ports, ports_description):
                menu.add_command(label=description, command=lambda com=port: self.var_port.set(com))
            self.var_port.set(ports[0])
        else:
            self.var_port.set('No ports found')

    def get_save_file(self):
        ''' Opens prompt for file for data to be saved
        Runs when button beside save file is pressed.
        '''

        save_file = tkFileDialog.asksaveasfilename(
            initialdir=self.entry_file.get(),
            defaultextension='.h5',
            filetypes=[
                ('HDF5 file', '*.h5 *.hdf5'),
                ('All files', '*.*')
            ]
        )
        self.entry_save.delete(0, 'end')
        self.entry_save.insert(0, save_file)

    def gui_util(self, option):
        ''' Updates GUI components
        Enable and disable components based on events to prevent bad stuff.
        '''

        if option == 'open':
            for i, obj in enumerate(self.obj_to_disable_at_open):
                # Determine current state of object                
                if obj['state'] == 'disabled':
                    self.obj_enabled_at_open[i] = False
                else:
                    self.obj_enabled_at_open[i] = True
                
                # Disable object
                obj['state'] = 'disabled'

            self.entry_serial_status['state'] = 'normal'
            self.entry_serial_status.delete(0, 'end')
            self.entry_serial_status.insert(0, 'Opening...')
            self.entry_serial_status['state'] = 'readonly'

        elif option == 'opened':
            # Enable start objects
            for obj in self.obj_to_enable_at_open:
                obj['state'] = 'normal'

            self.entry_serial_status['state'] = 'normal'
            self.entry_serial_status.delete(0, 'end')
            self.entry_serial_status.insert(0, 'Opened')
            self.entry_serial_status['state'] = 'readonly'

        elif option == 'close':
            for obj, to_enable in zip(self.obj_to_disable_at_open, self.obj_enabled_at_open):
                if to_enable: obj['state'] = 'normal'         # NOT SURE IF THAT'S CORRECT
            for obj in self.obj_to_enable_at_open:
                obj['state'] = 'disabled'

            self.entry_serial_status['state'] = 'normal'
            self.entry_serial_status.delete(0, 'end')
            self.entry_serial_status.insert(0, 'Closed')
            self.entry_serial_status['state'] = 'readonly'

        elif option == 'start':
            for obj in self.obj_to_disable_at_start:
                obj['state'] = 'disabled'
            for obj in self.obj_to_enable_at_start:
                obj['state'] = 'normal'

        elif option == 'stop':
            for obj in self.obj_to_disable_at_start:
                obj['state'] = 'normal'
            for obj in self.obj_to_enable_at_start:
                obj['state'] = 'disabled'

            self.entry_serial_status['state'] = 'normal'
            self.entry_serial_status.delete(0, 'end')
            self.entry_serial_status.insert(0, 'Closed')
            self.entry_serial_status['state'] = 'readonly'

    def open_serial(self, delay=3, timeout=5):
        ''' Open serial connection to Arduino
        Executes when 'Open' is pressed
        '''

        # Disable GUI components
        self.gui_util('open')

        # Open serial
        self.ser.port = self.var_port.get()
        try:
            self.ser.open()
        except serial.SerialException as err:
            # Error during serial.open()
            err_msg = err.args[0]
            tkMessageBox.showerror('Serial error', err_msg)
            print('Serial error: ' + err_msg)
            self.close_serial()
            self.gui_util('close')
            return
        else:
            # Serial opened successfully
            time.sleep(delay)
            self.gui_util('opened')
            if self.var_verbose.get(): print('Connection to Arduino opened')

        # Handle opening message from serial
        if self.var_print_arduino.get():
            while self.ser.in_waiting:
                sys.stdout.write(arduino_head + self.ser.readline())
        else:
            self.ser.flushInput()

        # Define parameters
        # NOTE: Order is important here since this order is preserved when sending via serial.
        self.parameters['pre_session'] = int(self.entry_pre_session.get())
        self.parameters['post_session'] = int(self.entry_post_session.get())
        self.parameters['trial_num'] = int(self.entry_trial_num.get())
        self.parameters['trial_duration'] = int(self.entry_trial_dur.get())
        self.parameters['iti'] = int(self.entry_iti.get())
        self.parameters['img_all'] = int(self.var_image_all.get())
        self.parameters['img_ttl_dur'] = int(self.entry_image_ttl_dur.get())
        self.parameters['track_period'] = int(self.entry_track_period.get())
        self.parameters['track_steps'] = int(self.entry_track_steps.get())

        # Send parameters and make sure it's processed
        values = self.parameters.values()
        if self.var_verbose.get(): print('Sending parameters: {}'.format(values))
        self.ser.write('+'.join(str(s) for s in values))

        start_time = time.time()
        while 1:
            if self.ser.in_waiting:
                if self.var_print_arduino.get():
                    # Print incoming data
                    while self.ser.in_waiting:
                        sys.stdout.write(arduino_head + self.ser.readline())
                print('Parameters uploaded to Arduino')
                print('Ready to start')
                return
            elif time.time() >= start_time + timeout:
                print('Error sending parameters to Arduino')
                print('Uploading timed out. Start signal not found.')
                self.gui_util('close')
                self.close_serial()
                return
    
    def close_serial(self):
        ''' Close serial connection to Arduino '''
        self.ser.close()
        self.gui_util('close')
        print('Connection to Arduino closed.')
    
    def start(self):
        self.gui_util('start')

        # Clear Queues
        for q in [self.q]:
            with q.mutex:
                q.queue.clear()

        session_length = self.parameters['pre_session'] + self.parameters['post_session'] + self.parameters['iti'] * self.parameters['trial_num']
        nstepframes = 2 * session_length / float(self.entry_track_period.get())

        # Create data file
        if self.entry_save.get():
            try:
                # Create file if it doesn't already exist ('x' parameter)
                self.data_file = h5py.File(self.entry_save.get(), 'x')
            except IOError:
                tkMessageBox.showerror('File error', 'Could not create file to save data.')
                self.gui_util('stop')
                self.gui_util('open')
                self.gui_util('opened')
                return
        else:
            if not os.path.exists('data'):
                os.makedirs('data')
            now = datetime.now()
            filename = 'data/data-' + now.strftime('%y%m%d-%H%M%S') + '.h5'
            self.data_file = h5py.File(filename, 'x')

        self.behav_grp = self.data_file.create_group('behavior')
        self.behav_grp.create_dataset(name='trials', dtype='uint32',
            shape=(1000, ), chunks=(1, ))
        self.behav_grp.create_dataset(name='trial_manual', dtype=bool,
            shape=(1000, ), chunks=(1, ))
        self.behav_grp.create_dataset(name='rail_leave', dtype='uint32',
            shape=(1000, ), chunks=(1, ))
        self.behav_grp.create_dataset(name='rail_home', dtype='uint32',
            shape=(1000, ), chunks=(1, ))
        self.behav_grp.create_dataset(name='steps', dtype='int32',
            shape=(2, int(nstepframes) * 1.1), chunks=(2, 1))
        self.behav_grp.create_dataset(name='track', dtype='int32',
            shape=(2, int(nstepframes) * 1.1), chunks=(2, 1))

        # Store session parameters into behavior group
        for key, value in self.parameters.iteritems():
            self.behav_grp.attrs[key] = value

        # Create thread to scan serial
        thread_scan = threading.Thread(
            target=scan_serial,
            args=(self.q, self.ser, self.var_print_arduino.get())
        )

        # Run session
        start_time = datetime.now()
        self.start_time = start_time.strftime('%H:%M:%S')
        print('Session start ~ {}'.format(self.start_time))
        self.behav_grp.attrs['start_time'] = self.start_time

        self.ser.flushInput()                                   # Remove data from serial input
        self.ser.write('E')                                     # Start signal for Arduino
        thread_scan.start()

        # Update GUI
        self.update_session()

    def update_session(self):
        # Checks Queue for incoming data from arduino. Data arrives as comma-separated values with the first element
        # ('code') defining the type of data.

        refresh_rate = 10  # Rate to update GUI. Should be faster than data coming in, eg tracking rate

        # End on 'Stop' button (by user)
        if self.var_stop.get():
            self.var_stop.set(False)
            self.ser.write('0')
            print('User triggered stop.')

        # Incoming queue has format:
        #   [code, ts [, extra values...]]
        while not self.q.empty():
            q_in = self.q.get()
            code = q_in[0]
            ts = q_in[1]

            # stop_session is called only when Arduino sends stop code
            if code == code_end:
                arduino_end = ts
                print('Stopping session.')
                self.stop_session(arduino_end)
                return

            elif code == code_trial_start:
                manual = bool(q_in[2])

                self.behav_grp['trials'][self.counter['trial']] = ts
                self.behav_grp['trial_manual'][self.counter['trial']] = manual

            elif code == code_rail_leave:
                self.behav_grp['rail_leave'][self.counter['trial']] = ts

            elif code == code_rail_home:
                self.behav_grp['rail_home'][self.counter['trial']] = ts
                self.counter['trial'] += 1

            elif code == code_steps:
                dist = int(q_in[2])

                # Record tracking
                self.behav_grp['steps'][:, self.counter['steps']] = [ts, dist]
                self.counter['steps'] += 1

            elif code == code_track:
                dist = int(q_in[2])

                # Record tracking
                self.behav_grp['track'][:, self.counter['track']] = [ts, dist]

                # Increment counter
                self.counter['track'] += 1

        self.parent.after(refresh_rate, self.update_session)

    def stop_session(self, frame_cutoff=None, arduino_end=None):
        end_time = datetime.now().strftime('%H:%M:%S')
        print('Session ended at ' + end_time)
        self.gui_util('stop')
        self.close_serial()

        if self.data_file:
            print('Writing behavioral data')
            self.behav_grp.attrs['end_time'] = end_time
            self.behav_grp['trials'].resize((self.counter['trial'], ))
            self.behav_grp['trial_manual'].resize((self.counter['trial'], ))
            self.behav_grp['rail_leave'].resize((self.counter['trial'], ))
            self.behav_grp['rail_home'].resize((self.counter['trial'], ))
            self.behav_grp['steps'].resize((2, self.counter['steps']))
            self.behav_grp['track'].resize((2, self.counter['track']))
            self.behav_grp.attrs['notes'] = self.scrolled_notes.get(1.0, 'end')
            self.behav_grp.attrs['arduino_end'] = arduino_end

            # Close HDF5 file object
            print('Closing file')
            self.data_file.close()
        
        # Clear self.parameters
        self.parameters = collections.OrderedDict()

        print('All done!')

        # Slack that session is done.
        if (self.entry_slack.get() and \
            slack):
            slack_msg(self.entry_slack.get(), 'Session ended.')


def slack_msg(slack_recipient, msg, test=False, verbose=False):
    '''Sends message through Slack
    Creates Slack message `msg` to `slack_recipient` from Bot.
    '''

    if not slack:
        print('No Slack client defined. Check environment variables.')
    else:
        bot_username = 'Conveyor bot'
        bot_icon = ':squirrel:'
        if test: msg='Test'

        try:
            slack.api_call(
              'chat.postMessage',
              username=bot_username,
              icon_emoji=bot_icon,
              channel=slack_recipient,
              text=msg
            )
        except:
            print('Unable to send Slack message')


def scan_serial(q_serial, ser, print_arduino=False, suppress=[]):
    #  Continually check serial connection for data sent from Arduino. Stop when '0 code' is received.

    code_end = 0

    if print_arduino: print('  Scanning Arduino outputs.')
    while 1:
        input_arduino = ser.readline()
        if not input_arduino: continue

        try:
            input_split = [int(x) for x in input_arduino.split(',')]
        except ValueError:
            # If not all comma-separated values are int castable
            if print_arduino: sys.stdout.write(arduino_head + input_arduino)
        else:
            if print_arduino and input_split[0] not in suppress:
                sys.stdout.write(arduino_head + input_arduino)
            if input_arduino: q_serial.put(input_split)
            if input_split[0] == code_end:
                if print_arduino: print("  Scan complete.")
                return


def main():
    # GUI
    root = tk.Tk()
    root.wm_title('Conveyor')
    InputManager(root)
    root.grid()
    root.mainloop()


if __name__ == '__main__':
    main()
