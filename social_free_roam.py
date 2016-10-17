
"""
Social conveyer
Randall Ung

Creates GUI to control behavioral and imaging devices for in vivo calcium
imaging. Script interfaces with Arduino microcontroller and imaging devices.
"""

from Tkinter import *
import tkMessageBox
import tkFileDialog
import collections
import serial
import serial.tools.list_ports
import threading
from Queue import Queue
from slacker import Slacker
import time
from datetime import datetime
from datetime import timedelta
import os
import sys
import h5py
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib.colors import LinearSegmentedColormap
from matplotlib import style
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2TkAgg
from matplotlib.figure import Figure
from matplotlib import gridspec
from matplotlib.collections import LineCollection
import seaborn as sns
import pdb


# Setup Slack
# Token is stored in text file 'key_file'
key_file = 'slack.txt'
if os.path.isfile(key_file):
    with open(key_file, 'r') as kf:
        slack = Slacker(kf.read())
else:
    slack = None


class InputManager(object):

    def __init__(self, parent):
        # GUI layout
        # parent
        # - parameter_frame
        #   + session_frame
        #     ~ core_session_frame
        #       - session_prop_frame
        #       - stim_frame
        #       - track_frame
        #     ~ opt_session_frame
        #       - distro_frame
        #         + minmax_frame
        #       - imaging_frame
        #   + start_frame
        #   + serial_frame
        #   + slack_frame
        # - monitor_frame
        #   + (figure)
        #   + scoreboard_frame
        #   + legend_frame

        entry_width = 10

        self.parent = parent
        parent.rowconfigure(0, weight=1)
        parent.rowconfigure(1, weight=2)
        parent.columnconfigure(0, weight=1)

        ###########################
        ##### PARAMETER FRAME #####
        ###########################
        parameter_frame = Frame(parent)
        parameter_frame.grid(row=0, column=0)
        Label(parameter_frame, text="Session parameters", font="-size 14").grid(row=0, column=0, columnspan=2)

        ###### SESSION SETTINGS FRAME ######
        session_frame = Frame(parameter_frame)
        session_frame.grid(row=1, column=0, rowspan=2, padx=15, pady=5)

        core_session_frame = Frame(session_frame)
        core_session_frame.grid(row=0, column=0)

        # Session frame
        session_prop_frame = Frame(core_session_frame)
        session_prop_frame.grid(row=0, column=0, sticky=E, padx=15, pady=5)
        self.entry_session_dur = Entry(session_prop_frame, width=entry_width)
        self.entry_presession = Entry(session_prop_frame, width=entry_width)
        self.entry_postsession = Entry(session_prop_frame, width=entry_width)
        Label(session_prop_frame, text="Session duration: ", anchor=E).grid(row=0, column=0, sticky=E)
        Label(session_prop_frame, text="Pre-session minimum (ms): ", anchor=E).grid(row=1, column=0, sticky=E)
        Label(session_prop_frame, text="Post-session minimum (ms): ", anchor=E).grid(row=2, column=0, sticky=E)
        self.entry_session_dur.grid(row=0, column=1, sticky=W)
        self.entry_presession.grid(row=1, column=1, sticky=W)
        self.entry_postsession.grid(row=2, column=1, sticky=W)

        # Stim frame
        stim_frame = Frame(core_session_frame)
        stim_frame.grid(row=1, column=0, sticky=E, padx=15, pady=5)
        self.entry_interaction_dur = Entry(stim_frame, width=entry_width)
        self.entry_reset_cue_dur = Entry(stim_frame, width=entry_width)
        self.entry_reset_cue_freq = Entry(stim_frame, width=entry_width)
        Label(stim_frame, text="Interaction duration (ms): ", anchor=E).grid(row=0, column=0, sticky=E)
        Label(stim_frame, text="Reset cue duration (ms): ", anchor=E).grid(row=1, column=0, sticky=E)
        Label(stim_frame, text="Reset frequency (Hz): ", anchor=E).grid(row=2, column=0, sticky=E)
        self.entry_interaction_dur.grid(row=0, column=1, sticky=W)
        self.entry_reset_cue_dur.grid(row=1, column=1, sticky=W)
        self.entry_reset_cue_freq.grid(row=2, column=1, sticky=W)

        # Track frame
        track_frame = Frame(core_session_frame)
        track_frame.grid(row=2, column=0, sticky=E, padx=15, pady=5)
        self.entry_track_period = Entry(track_frame, width=entry_width)
        self.entry_step_threshold = Entry(track_frame, width=entry_width)
        self.entry_step_shift = Entry(track_frame, width=entry_width)
        Label(track_frame, text="Track period (ms): ", anchor=E).grid(row=0, column=0, sticky=E)
        Label(track_frame, text="Step threshold: ", anchor=E).grid(row=1, column=0, sticky=E)
        Label(track_frame, text="Step shift: ", anchor=E).grid(row=2, column=0, sticky=E)
        self.entry_track_period.grid(row=0, column=1, sticky=W)
        self.entry_step_threshold.grid(row=1, column=1, sticky=W)
        self.entry_step_shift.grid(row=2, column=1, sticky=W)
        
        # Optional settings frame
        opt_session_frame = Frame(session_frame)
        opt_session_frame.grid(row=0, column=1)

        imaging_frame = LabelFrame(opt_session_frame, text="Imaging")
        imaging_frame.grid(row=1, column=0, padx=10, pady=5, sticky=W+E)
        self.image_var = IntVar()
        self.radio_img_trial = Radiobutton(imaging_frame, text="Image by trial", variable=self.image_var, value=0)
        self.radio_img_trial.grid(row=0, column=0, sticky=W)
        self.radio_img_all = Radiobutton(imaging_frame, text="Image all", variable=self.image_var, value=1)
        self.radio_img_all.grid(row=1, column=0, sticky=W)

        debug_frame = LabelFrame(opt_session_frame, text="Debugging")
        debug_frame.grid(row=2, column=0, padx=10, pady=5, sticky=W+E)
        self.print_var = BooleanVar()
        self.check_print = Checkbutton(debug_frame, text="Print Arduino output", variable=self.print_var)
        self.check_print.grid(row=0, column=0)

        ###### SERIAL FRAME ######
        serial_frame = Frame(parameter_frame)
        serial_frame.grid(row=1, column=1, padx=5, pady=5, sticky=W+E)
        self.ser = None
        self.port_var = StringVar()

        serial_ports_frame = Frame(serial_frame)
        serial_ports_frame.grid(row=0, column=0, columnspan=2, sticky=W)
        Label(serial_ports_frame, text="Serial port:").grid(row=0, column=0, sticky=E, padx=5)
        self.option_ports = OptionMenu(serial_ports_frame, self.port_var, [])
        self.option_ports.grid(row=0, column=1, sticky=W+E, padx=5)
        Label(serial_ports_frame, text="Serial status:").grid(row=1, column=0, sticky=E, padx=5)
        self.entry_serial_status = Entry(serial_ports_frame)
        self.entry_serial_status.grid(row=1, column=1, sticky=W, padx=5)
        self.entry_serial_status['state'] = NORMAL
        self.entry_serial_status.insert(0, 'Closed')
        self.entry_serial_status['state'] = 'readonly'

        open_close_frame = Frame(serial_frame)
        open_close_frame.grid(row=1, column=0, columnspan=2, pady=10)
        self.button_open_port = Button(open_close_frame, text="Open", command=self.open_serial)
        self.button_close_port = Button(open_close_frame, text="Close", command=self.close_serial)
        self.button_update_ports = Button(open_close_frame, text="Update", command=self.update_ports)
        self.button_open_port.grid(row=0, column=0, pady=5)
        self.button_close_port.grid(row=0, column=1, padx=10, pady=5)
        self.button_update_ports.grid(row=0, column=2, pady=5)

        ###### SLACK FRAME #####
        slack_frame = Frame(parameter_frame)
        slack_frame.grid(row=2, column=1, padx=5, pady=5, sticky=W+E)
        Label(slack_frame, text="Slack address for notifications: ", anchor=W).grid(row=0, column=0, sticky=W+E)
        self.entry_slack = Entry(slack_frame)
        self.entry_slack.grid(row=1, column=0, sticky=N+S+W+E)
        self.button_slack = Button(slack_frame, text="Test", command=lambda: slack_msg(self.entry_slack.get(), "Test", test=True))
        self.button_slack.grid(row=1, column=1, padx=5, sticky=W)

        ##### START FRAME #####
        start_frame = Frame(parameter_frame)
        start_frame.grid(row=3, column=0, columnspan=2, padx=5, pady=15, sticky=W+E)
        start_frame.columnconfigure(0, weight=4)

        Label(start_frame, text="File to save data:", anchor=W).grid(row=0, column=0, sticky=W)
        self.stop = BooleanVar()
        self.stop.set(False)
        self.entry_save = Entry(start_frame)
        self.button_save_file = Button(start_frame, text="...", command=self.get_save_file)
        self.button_start = Button(start_frame, text="Start", command=lambda: self.parent.after(0, self.start))
        self.button_stop = Button(start_frame, text="Stop", command=lambda: self.stop.set(True))
        self.entry_save.grid(row=1, column=0, sticky=N+S+W+E)
        self.button_save_file.grid(row=1, column=1, padx=5)
        self.button_start.grid(row=1, column=2, sticky=N+S, padx=5)
        self.button_stop.grid(row=1, column=3, sticky=N+S, padx=5)

        ###########################
        ###### MONITOR FRAME ######
        ###########################
        monitor_frame = Frame(parent, bg='white')
        monitor_frame.grid(row=1, column=0, sticky=W+E+N+S)
        monitor_frame.columnconfigure(0, weight=4)
        Label(monitor_frame, text="Session events", bg='white', font="-size 16")\
            .grid(row=0, column=0, columnspan=2, pady=10)

        ##### PLOTS #####
        self.num_rail_segments = 10  # Number of segments to split rail--for plotting
        trial_window = 30000

        sns.set_style('dark')
        self.color_csplus  = 'steelblue'
        self.color_csminus  = 'coral'
        self.color_track    = 'forestgreen'
        self.color_rail_end = 'black'
        self.color_grays = [np.array([1, 1, 1], dtype=float) * n / self.num_rail_segments \
                            for n in np.arange(self.num_rail_segments)]

        self.fig = Figure()
        gs = gridspec.GridSpec(10, 1)
        self.ax_total = self.fig.add_subplot(gs[0, :])
        self.ax_histo = self.fig.add_subplot(gs[1:3, :])
        self.ax_raster = self.fig.add_subplot(gs[3:, :])

        # Session progression
        self.ax_total.tick_params(axis='both',
                                  left='off', right='off', bottom='off', top='off',
                                  labelleft='off')
        self.ax_total.set_title("Session progression (trials)")

        # Trial histogram
        # Create CDF for each variable.
        self.ax_histo.set_ylabel("Probability")
        self.ax_histo.set_ylim(0, 1)
        self.ax_histo.set_xlim(0, trial_window)
        self.ax_histo.tick_params(axis='both',
                                  left='off', right='off', bottom='off', top='off',
                                  labelleft='off', labelbottom='off')
        self.histo_rail_end = self.ax_histo.plot([], [], color=self.color_rail_end)
        self.histo_lines = [self.histo_rail_end]  # List of all lines in trial histogram

        # Raster plots
        # Create segmented line plots broken by np.nan values.
        # self.raster_steps uses LineCollection instead to set different colors for each segment.
        self.ax_raster.tick_params(axis='y', left='off', right='off', labelleft='off')
        self.ax_raster.set_xlabel("Trial time (ms)")
        self.ax_raster.set_ylabel("Trials")
        self.ax_raster.set_xlim(0, trial_window)

        self.raster_track = self.ax_raster.plot([], [], c=self.color_track)
        # self.raster_steps = self.ax_steps.plot([], [], c=(1, 1, 1))  # will scale colors to black
        self.raster_rail_end = self.ax_raster.plot([], [], c=self.color_rail_end)
        self.raster_lines = [self.raster_track,
                             # self.raster_steps,
        					 self.raster_rail_end]
        segments = [[(xi, 0), (xi, 1)] for xi in np.arange(self.num_rail_segments)]
        self.raster_steps = LineCollection([], colors=self.color_grays)
        self.ax_raster.add_collection(self.raster_steps)

        self.plot_canvas = FigureCanvasTkAgg(self.fig, monitor_frame)
        # self.plot_canvas.get_tk_widget().configure(background='black')  # retrieves "SystemButtonFace" for some reason
        self.fig.tight_layout()
        self.plot_canvas.show()
        self.plot_canvas.get_tk_widget().grid(row=1, column=0, rowspan=2, sticky=W+E+N+S)

        ##### LEGEND #####
        legend_frame = Frame(monitor_frame, bg='white')
        legend_frame.grid(row=2, column=1)
        Label(legend_frame, text=u'\u25ac', fg='gray', bg='white').grid(row=0, column=0)
        Label(legend_frame, text='Rail progression', bg='white', anchor=W).grid(row=0, column=1, sticky=W)
        Label(legend_frame, text=u'\u25ac', fg=self.color_rail_end, bg='white').grid(row=1, column=0)
        Label(legend_frame, text='Rail end', bg='white', anchor=W).grid(row=1, column=1, sticky=W)

        ##### SCOREBOARD #####
        scoreboard_frame = Frame(monitor_frame, bg='white')
        scoreboard_frame.grid(row=1, column=1, padx=20, sticky=N)
        self.entry_end = Entry(scoreboard_frame, width=entry_width)
        self.entry_rail_ends = Entry(scoreboard_frame, width=entry_width)
        Label(scoreboard_frame, text="Session end:", bg='white', anchor=W).grid(row=0, sticky=W)
        Label(scoreboard_frame, text="Rail ends:", bg='white', anchor=W).grid(row=2, sticky=W)
        self.entry_end.grid(row=1, sticky=W)
        self.entry_rail_ends.grid(row=3, sticky=W)

        self.scoreboard_objs = [self.entry_end,
                                self.entry_rail_ends]
        
        ###### GUI OBJECTS ORGANIZED BY TIME ACTIVE ######
        # List of components to disable at open
        self.obj_to_disable_at_open = [self.option_ports,
                                       self.button_update_ports,
                                       self.button_open_port,
                                       self.entry_session_dur,
                                       self.entry_presession,
                                       self.entry_postsession,
                                       self.entry_interaction_dur,
                                       self.entry_reset_cue_dur,
                                       self.entry_reset_cue_freq,
                                       self.entry_track_period,
                                       self.entry_step_threshold,
                                       self.entry_step_shift,
                                       self.radio_img_trial,
                                       self.radio_img_all,
                                       self.check_print]
        # Boolean of objects in list above that should be enabled when time...
        self.obj_enabled_at_open = [False] * len(self.obj_to_disable_at_open)
        
        self.obj_to_enable_at_open = [self.button_close_port,
                                      self.button_start]
        self.obj_to_disable_at_start = [self.button_close_port,
                                        self.entry_save,
                                        self.button_save_file,
                                        self.button_start,
                                        self.button_slack]
        self.obj_to_enable_at_start = [self.button_stop]

        # Update list of available ports
        self.update_ports()

        # Default values
        self.entry_session_dur.insert(0, 1800000)
        self.entry_presession.insert(0, 60000)
        self.entry_postsession.insert(0, 60000)
        self.entry_interaction_dur.insert(0, 10000)
        self.entry_reset_cue_dur.insert(0, 1000)
        self.entry_reset_cue_freq.insert(0, 10000)
        self.entry_track_period.insert(0, 50)
        self.entry_step_threshold.insert(0, 0)
        self.entry_step_shift.insert(0, 1)
        self.image_var.set(1)
        self.print_var.set(True)
        self.button_close_port['state'] = DISABLED
        # self.entry_slack.insert(0, "@randall")
        self.button_start['state'] = DISABLED
        self.button_stop['state'] = DISABLED

        ###### SESSION VARIABLES ######
        self.parameters = collections.OrderedDict()
        self.ser = serial.Serial(timeout=1, baudrate=9600)
        self.start_time = ""
        self.track = np.empty(0)
        self.rail_end = np.empty(0)
        self.counter = {}
        self.q = Queue()

    def update_ports(self):
        ports_info = list(serial.tools.list_ports.comports())
        ports = [port.device for port in ports_info]
        ports_description = [port.description for port in ports_info]

        menu = self.option_ports['menu']
        menu.delete(0, END)
        if ports:
            for port, description in zip(ports, ports_description):
                menu.add_command(label=description, command=lambda com=port: self.port_var.set(com))
            self.port_var.set(ports[0])
        else:
            self.port_var.set("No ports found")

    def distro_toggle(self, uniform):
        parts = [self.entry_minITI, self.entry_maxITI]
        for part in parts:
            if uniform: part["state"] = DISABLED
            else: part["state"] = NORMAL

    def get_save_file(self):
        save_file = tkFileDialog.asksaveasfilename(defaultextension=".h5",
                                                   filetypes=[("HDF5 file", "*.h5 *.hdf5"),
                                                              ("All files", "*.*")])
        self.entry_save.delete(0, END)
        self.entry_save.insert(0, save_file)

    def gui_util(self, option):
        # Updates GUI components.
        # Enable and disable components based on events.

        if option == 'open':
            for i, obj in enumerate(self.obj_to_disable_at_open):
                # Determine current state of object                
                if obj['state'] == DISABLED:
                    self.obj_enabled_at_open[i] = False
                else:
                    self.obj_enabled_at_open[i] = True
                
                # Disable object
                obj['state'] = DISABLED

            self.entry_serial_status.config(state=NORMAL, fg='red')
            self.entry_serial_status.delete(0, END)
            self.entry_serial_status.insert(0, 'Opening...')
            self.entry_serial_status['state'] = 'readonly'

        elif option == 'opened':
            # Enable start objects
            for obj in self.obj_to_enable_at_open:
                obj['state'] = NORMAL

            self.entry_serial_status.config(state=NORMAL, fg='black')
            self.entry_serial_status.delete(0, END)
            self.entry_serial_status.insert(0, 'Opened')
            self.entry_serial_status['state'] = 'readonly'

        elif option == 'close':
            for obj, to_enable in zip(self.obj_to_disable_at_open, self.obj_enabled_at_open):
                if to_enable: obj['state'] = NORMAL         # NOT SURE IF THAT'S CORRECT
            for obj in self.obj_to_enable_at_open:
                obj['state'] = DISABLED

            self.entry_serial_status.config(state=NORMAL, fg='black')
            self.entry_serial_status.delete(0, END)
            self.entry_serial_status.insert(0, 'Closed')
            self.entry_serial_status['state'] = 'readonly'

        elif option == 'start':
            for obj in self.obj_to_disable_at_start:
                obj['state'] = DISABLED
            for obj in self.obj_to_enable_at_start:
                obj['state'] = NORMAL

        elif option == 'stop':
            for obj in self.obj_to_disable_at_start:
                obj['state'] = NORMAL
            for obj in self.obj_to_enable_at_start:
                obj['state'] = DISABLED

            self.entry_serial_status.config(state=NORMAL, fg='black')
            self.entry_serial_status.delete(0, END)
            self.entry_serial_status.insert(0, 'Closed')
            self.entry_serial_status['state'] = 'readonly'

    def open_serial(self):
        # Executes when "Open" is pressed

        # Disable GUI components
        self.gui_util('open')

        # Checkpoint #1
        # - Serial port
        # - Save file
        # - Slack
        print "\nChecking parameters."
        # if self.port_var.get() == "No ports found":
        #     tkMessageBox.showerror("Serial error", "No port selected. Make sure Arduino is plugged in.")
        #     print "No ports found. Please attach Arduino or check connection."
        #     self.gui_util('close')
        #     return

        # Define parameters
        # NOTE: Order is important here since this order is preserved when sending via serial.
        self.parameters['session_duration'] = int(self.entry_session_dur.get())
        self.parameters['presession_window'] = int(self.entry_presession.get())
        self.parameters['postsession_window'] = int(self.entry_postsession.get())
        self.parameters['interaction_duration'] = int(self.entry_interaction_dur.get())
        self.parameters['reset_cue_duration'] = int(self.entry_reset_cue_dur.get())
        self.parameters['reset_cue_frequency'] = int(self.entry_reset_cue_freq.get())
        self.parameters['image_all'] = int(self.image_var.get())
        self.parameters['track_period'] = int(self.entry_track_period.get())
        self.parameters['step_threshold'] = int(self.entry_step_threshold.get())
        self.parameters['step_shift'] = int(self.entry_step_shift.get())

        # Clear old data
        self.ax_total.cla()
        for line in self.histo_lines:
            line[0].set_xdata([])
            line[0].set_ydata([])
        for line in self.raster_lines:
            line[0].set_data([[], []])
        self.plot_canvas.draw()
        for obj in self.scoreboard_objs:
            obj.delete(0, END)

        # Set axis for "trial" plots
        self.ax_histo.set_xlim(0, 30000)
        self.ax_raster.set_ylim(20, 0)
        self.ax_raster.set_xlim(0, 30000)
        
        # Create "blank" LineCollection to be filled later
        # blank_segments = [np.array([[-1, yi], [-1, yi+1]]) for yi in np.arange(trial_num) \
        #                                                    for _ in np.arange(self.num_rail_segments)]
        # self.raster_steps.set_segments(blank_segments)
        
        # Initialize/clear old data
        self.trial_onset = np.zeros(1000, dtype='uint32')
        self.steps = np.zeros((2, 360000), dtype='uint32')
        self.track = np.zeros((2, 360000), dtype='int32')
        self.rail_end = np.zeros(int(self.parameters['session_duration']/10), dtype='uint32')
        self.counter = {'trial': 0,
                        'rail_end': 0,
                        'track': 0,
                        'steps': 0}

        # Open serial and upload to Arduino
        self.ser.port = self.port_var.get()
        ser_return = start_arduino(self.ser, self.parameters)
        if ser_return:
            tkMessageBox.showerror("Serial error",
                                   "{0}: {1}\n\nCould not create serial connection."\
                                   .format(ser_return.errno, ser_return.strerror))
            print "\n{0}: {1}\nCould not create serial connection. Check port is open."\
                  .format(ser_return.errno, ser_return.strerror)
            self.close_serial  ## MIGHT NOT WORK BC SERIAL DIDN'T OPEN...
            self.gui_util('close')
            return

        self.gui_util('opened')
        print "Waiting for start command."
    
    def close_serial(self):
        self.ser.close()
        self.gui_util('close')
        print "Connection to Arduino closed."
    
    def start(self):
        self.gui_util('start')

        # Finish setup
        if self.entry_save.get():
            try:
                # Create file if it doesn't already exist ('x' parameter)
                data_file = h5py.File(self.entry_save.get(), 'x')
            except IOError:
                tkMessageBox.showerror("File error", "Could not create file to save data.")
                self.gui_util('stop')
                self.gui_util('open')
                self.gui_util('opened')
                return
        else:
            if not os.path.exists('data'):
                os.makedirs('data')
            now = datetime.now()
            filename = 'data/data-' + now.strftime('%y%m%d-%H%M%S') + '.h5'
            data_file = h5py.File(filename, 'x')
        
        # Run session
        self.ser.flushInput()                                   # Remove data from serial input
        self.ser.write('E')                                     # Start signal for Arduino
        self.start_time = datetime.now().strftime("%H:%M:%S")
        print "Session start ~ " + self.start_time

        # Create thread to scan serial
        thread_scan = threading.Thread(target=scan_serial,
                                       args=(self.q, self.ser, self.parameters, self.print_var.get()))
        thread_scan.start()

        # Update GUI alongside Arduino scanning (scan_serial on separate thread)
        self.update_session(data_file)

    def update_session(self, data_file):
        # Checks Queue for incoming data from arduino. Data arrives as comma-separated values with the first element
        # ('code') defining the type of data.

        refresh_rate = 10  # Rate to update GUI. Should be faster than data coming in, eg tracking rate
        steps_per_rail = 600  # Number of steps by stepper to traverse entire rail
        rail_milestones = (np.arange(self.num_rail_segments, dtype=float) + 1) * steps_per_rail / self.num_rail_segments

        # Codes
        code_end = 0
        code_conveyer_steps = 1
        code_rail_end = 2
        code_trial_start = 3
        code_session_length = 6
        code_track = 7

        # End on "Stop" button (by user)
        if self.stop.get():
            self.stop.set(False)
            self.ser.write("0")
            print "Stopped by user."
            
            # Calculate time (H:M:S) when session ends
            # end_time = datetime.now()                                       # MAKE SURE CORRECT!!!
            # self.entry_end.delete(0, END)
            # self.entry_end.insert(0, end_time.strftime("%H:%M:%S") + " by user")
            
            # self.stop_session(ser, parameters, data_file)
            # return

        # Incoming queue has format:
        #   [code, ts [, extra values...]]
        if not self.q.empty():
            q_in = self.q.get()
            code = q_in[0]
            ts = q_in[1]

            if code == code_end:
                self.parameters['arduino_end'] = ts
                self.stop_session(data_file)
                return

            elif code == code_conveyer_steps:
                dist = int(q_in[2])

                # Record steps
                self.steps[:, self.counter['steps']] = [ts, dist]
                # self.steps_by_trial[self.counter['trial']] += dist

                # Increment counter
                self.counter['steps'] += 1

            elif code == code_rail_end:
                # Record time end of rail reached
                self.rail_end[self.counter['rail_end']] = ts

                # Update scoreboard
                self.entry_rail_ends.delete(0, END)
                self.entry_rail_ends.insert(0, np.count_nonzero(self.rail_end))

                self.counter['rail_end'] += 1

            elif code == code_trial_start:
                self.trial_onset[self.counter['trial']] = ts
                self.counter['trial'] += 1

            elif code == code_session_length:
                # Length of session
                session_length = int(q_in[2])

                # Adjust x-axis of "total" plot
                self.ax_total.set_xlim(0, session_length)
                self.ax_total.set_xticks([0, session_length])
                self.ax_total.set_ylim(0, 2)
                self.plot_canvas.draw()

                # Update scoreboard
                # Calculate time (H:M:S) when session ends
                end_time = datetime.now() + timedelta(seconds=session_length/1000)
                self.entry_end.delete(0, END)
                self.entry_end.insert(0, end_time.strftime("%H:%M:%S"))

            elif code == code_track:
                dist = int(q_in[2])

                # Record tracking
                self.track[:, self.counter['track']] = [ts, dist]
                
                # Increment counter
                self.counter['track'] += 1

        self.parent.after(refresh_rate, self.update_session, data_file)

    def stop_session(self, data_file):
        self.gui_util('stop')
        self.close_serial()
        end_time = datetime.now().strftime("%H:%M:%S")

        if data_file:
            behav_grp = data_file.create_group('behavior')
            behav_grp.create_dataset(name='trials', data=self.trial_onset[:self.counter['trial']], dtype='uint32')
            behav_grp.create_dataset(name='steps', data=self.steps[:, :self.counter['steps']], dtype='uint32')
            # behav_grp.create_dataset(name='steps_by_trial', data=self.steps_by_trial, dtype='uint32')
            behav_grp.create_dataset(name='track', data=self.track[:, :self.counter['track']], dtype='int32')
            behav_grp.create_dataset(name='rail_end', data=self.rail_end[:self.counter['rail_end']], dtype='uint32')

            # Store session parameters into behavior group
            behav_grp.attrs['start_time'] = self.start_time
            behav_grp.attrs['end_time'] = end_time
            for key, value in self.parameters.iteritems():
                behav_grp.attrs[key] = value
            
            # Close HDF5 file object
            data_file.close()
        
        # Clear self.parameters
        self.parameters = collections.OrderedDict()

        print "Session ended at " + end_time

        # Slack that session is done.
        if self.entry_slack.get() and \
           slack:
            slack_msg(self.entry_slack.get(), "Session ended.")


# def slack_test(slack_recipient, msg):
#     # Creates Slack message to slack_recipient from Bot. Message is string msg.

#     # Verify Slack recipient
#     if not slack_recipient:
#         return
#     slack_code = slack_recipient[0]
#     slack_name = slack_recipient[1::]
#     if slack_code is '@':
#         slack_users = slack.users.list().body['members']
#         slack_user_names = [user['name'] for user in slack_users]
#         if slack_name not in slack_user_names:
#             tkMessageBox.showerror("Slack error", "Slack user does not exist")
#     elif slack_code is '#':
#         slack_channels = slack.channels.list().body['members']
#         slack_channel_names = [channel['name'] for channel in slack_channels]
#         if slack_name not in slack_channel_names:
#             tkMessageBox.showerror("Slack error", "Slack channel does not exist")
#     else:
#         tkMessageBox.showerror("Slack error", "Slack recipient is invalid.")

#     if msg:
#         slack.chat.post_message(slack_recipient, msg,
#                                 username="Social conveyer bot",
#                                 icon_emoji=":squirrel:")


def slack_msg(slack_recipient, msg, test=False):
    # Creates Slack message to slack_recipient from Bot. Message is string msg.
    bot_username = "Social conveyer bot"
    bot_icon = ":squirrel:"

    # Verify Slack recipient
    if not slack_recipient:
        return
    slack_code = slack_recipient[0]
    slack_name = slack_recipient[1::]
    if slack_code is '@':
        slack_users = slack.users.list().body['members']
        slack_user_names = [user['name'] for user in slack_users]
        if slack_name not in slack_user_names:
            if test:
                tkMessageBox.showerror("Slack error", "Slack user does not exist")
            else:
                print "Slack user does not exist. Message failed to send."
    elif slack_code is '#':
        slack_channels = slack.channels.list().body['members']
        slack_channel_names = [channel['name'] for channel in slack_channels]
        if slack_name not in slack_channel_names:
            if test:
                tkMessageBox.showerror("Slack error", "Slack channel does not exist")
            else:
                print "Slack channel does not exist. Message failed to send."
    else:
        if test:
            tkMessageBox.showerror("Slack error", "Slack recipient is invalid.")
        else:
            print "Slack recipient invalid. Message failed to send."
        return

    if msg:
        slack.chat.post_message(slack_recipient, msg,
                                username=bot_username,
                                icon_emoji=bot_icon)


def start_arduino(ser, parameters):

    values = parameters.values()
    print values
    sys.stdout.write("Uploading parameters to Arduino")
    sys.stdout.flush()
    
    try:
        ser.open()
    except serial.SerialException as err:
        sys.stdout.write("\nFailed to open connection.\n")
        return err

    # WAIT FOR ARDUINO TO ESTABLISH SERIAL CONNECTION
    timeout = 10
    timeout_count = 0
    while 1:
        if timeout_count >= timeout:
            sys.stdout.write(" connection timed out.\n")
            sys.stdout.flush()
            return serial.SerialException
        sys.stdout.write(".")
        sys.stdout.flush()
        if ser.read(): break
        timeout_count += 1

    ser.flushInput()            # Remove opening message from serial
    ser.write('+'.join(str(s) for s in values))
    while 1:
        if timeout_count >= timeout:
            sys.stdout.write(" connection timed out.\n")
            sys.stdout.flush()
            return serial.SerialException
        sys.stdout.write(".")
        sys.stdout.flush()
        if ser.read(): break
    print "\nArduino updated."

    return 0


def scan_serial(q, ser, parameters, print_arduino=False):
    #  Continually check serial connection for data sent from Arduino. Stop when "0 code" is received.

    code_end = 0

    if print_arduino: print "  Scanning Arduino outputs."
    while 1:
        input_arduino = ser.readline()
        if input_arduino == '': continue
        if print_arduino: sys.stdout.write('  [a]: ' + input_arduino)

        try:
            input_split = map(int, input_arduino.split(','))
        except ValueError:
            # If not all comma-separated values are int castable
            pass
        else:
            if input_arduino: q.put(input_split)
            if input_split[0] == code_end: 
                if print_arduino: print "  Scan complete."
                return


def main():
    # GUI
    root = Tk()
    root.wm_title("Social conveyer")
    if os.name == 'nt':
        root.iconbitmap(os.path.join(os.getcwd(), 'neuron.ico'))
    InputManager(root)
    root.mainloop()


if __name__ == '__main__':
    main()
