
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
with open(key_file, 'r') as kf:
    slack = Slacker(kf.read())


class InputManager(object):

    def __init__(self, parent):
        # GUI layout
        # parent
        # - parameter_frame
        #   + session_frame
        #     ~ core_session_frame
        #       - trial_frame
        #       - iti_frame
        #       - stim_frame
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

        # Trial frame
        trial_frame = Frame(core_session_frame)
        trial_frame.grid(row=1, column=0, sticky=E, padx=15, pady=5)
        self.entry_csplus = Entry(trial_frame, width=entry_width)
        self.entry_csminus = Entry(trial_frame, width=entry_width)
        self.entry_presession = Entry(trial_frame, width=entry_width)
        self.entry_postsession = Entry(trial_frame, width=entry_width)
        self.entry_trial_dur = Entry(trial_frame, width=entry_width)
        Label(trial_frame, text="Number of CS+: ", anchor=E).grid(row=0, column=0, sticky=E)
        Label(trial_frame, text="Number of CS-: ", anchor=E).grid(row=1, column=0, sticky=E)
        Label(trial_frame, text="Pre-session minimum (ms): ", anchor=E).grid(row=2, column=0, sticky=E)
        Label(trial_frame, text="Post-session minimum (ms): ", anchor=E).grid(row=3, column=0, sticky=E)
        Label(trial_frame, text="Trial duration (ms): ", anchor=E).grid(row=4, column=0, sticky=E)
        self.entry_csplus.grid(row=0, column=1, sticky=W)
        self.entry_csminus.grid(row=1, column=1, sticky=W)
        self.entry_presession.grid(row=2, column=1, sticky=W)
        self.entry_postsession.grid(row=3, column=1, sticky=W)
        self.entry_trial_dur.grid(row=4, column=1, sticky=W)
        
        # ITI frame
        iti_frame = Frame(core_session_frame)
        iti_frame.grid(row=2, column=0, sticky=E, padx=15, pady=5)
        self.entry_meanITI = Entry(iti_frame, width=entry_width)
        Label(iti_frame, text="Mean ITI (ms): ", anchor=E).grid(row=0, column=0, sticky=E)
        self.entry_meanITI.grid(row=0, column=1, sticky=W)

        # Stim frame
        stim_frame = Frame(core_session_frame)
        stim_frame.grid(row=3, column=0, sticky=E, padx=15, pady=5)
        self.entry_csplus_dur = Entry(stim_frame, width=entry_width)
        self.entry_csplus_freq = Entry(stim_frame, width=entry_width)
        self.entry_csminus_dur = Entry(stim_frame, width=entry_width)
        self.entry_csminus_freq = Entry(stim_frame, width=entry_width)
        Label(stim_frame, text="CS+ duration (ms): ", anchor=E).grid(row=0, column=0, sticky=E)
        Label(stim_frame, text="CS+ frequency (Hz): ", anchor=E).grid(row=1, column=0, sticky=E)
        Label(stim_frame, text="CS- duration (ms): ", anchor=E).grid(row=2, column=0, sticky=E)
        Label(stim_frame, text="CS- frequency (Hz): ", anchor=E).grid(row=3, column=0, sticky=E)
        self.entry_csplus_dur.grid(row=0, column=1, sticky=W)
        self.entry_csplus_freq.grid(row=1, column=1, sticky=W)
        self.entry_csminus_dur.grid(row=2, column=1, sticky=W)
        self.entry_csminus_freq.grid(row=3, column=1, sticky=W)
        
        # Optional settings frame
        opt_session_frame = Frame(session_frame)
        opt_session_frame.grid(row=0, column=1)

        distro_frame = LabelFrame(opt_session_frame, text="ITI distribution")
        distro_frame.grid(row=0, column=0, padx=10, pady=5, sticky=W+E)
        self.distro_var = IntVar()
        self.radio_uniform = Radiobutton(distro_frame, text="uniform", variable=self.distro_var, value=1,
                             command=lambda: self.distro_toggle(1))
        self.radio_uniform.grid(row=0, column=0, sticky=W, padx=5)
        self.radio_exp = Radiobutton(distro_frame, text="exponential", variable=self.distro_var, value=0,
                         command=lambda: self.distro_toggle(0))
        self.radio_exp.grid(row=1, column=0, sticky=W, padx=5)
        minmax_frame = Frame(distro_frame)
        minmax_frame.grid(row=2, padx=10, pady=5)
        self.entry_minITI = Entry(minmax_frame, width=entry_width)
        self.entry_maxITI = Entry(minmax_frame, width=entry_width)
        Label(minmax_frame, text="Min ITI:", anchor=E).grid(row=0, column=0, sticky=E)
        Label(minmax_frame, text="Max ITI:", anchor=E).grid(row=1, column=0, sticky=E)
        self.entry_minITI.grid(row=0, column=1, sticky=W)
        self.entry_maxITI.grid(row=1, column=1, sticky=W)

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
        self.button_slack = Button(slack_frame, text="Test", command=lambda: slack_test(self.entry_slack.get(), "Test"))
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
        Label(legend_frame, text=u'\u25ac', fg=self.color_csplus, bg='white').grid(row=0, column=0)
        Label(legend_frame, text='CS+', bg='white', anchor=W).grid(row=0, column=1, sticky=W)
        Label(legend_frame, text=u'\u25ac', fg=self.color_csminus, bg='white').grid(row=1, column=0)
        Label(legend_frame, text='CS-', bg='white', anchor=W).grid(row=1, column=1, sticky=W)
        Label(legend_frame, text=u'\u25ac', fg='gray', bg='white').grid(row=2, column=0)
        Label(legend_frame, text='Rail progression', bg='white', anchor=W).grid(row=2, column=1, sticky=W)
        Label(legend_frame, text=u'\u25ac', fg=self.color_rail_end, bg='white').grid(row=3, column=0)
        Label(legend_frame, text='Rail end', bg='white', anchor=W).grid(row=3, column=1, sticky=W)

        ##### SCOREBOARD #####
        scoreboard_frame = Frame(monitor_frame, bg='white')
        scoreboard_frame.grid(row=1, column=1, padx=20, sticky=N)
        self.entry_end = Entry(scoreboard_frame, width=entry_width)
        self.entry_trial_ct = Entry(scoreboard_frame, width=entry_width)
        self.entry_nextTrial = Entry(scoreboard_frame, width=entry_width)
        self.entry_rail_ends = Entry(scoreboard_frame, width=entry_width)
        Label(scoreboard_frame, text="Session end:", bg='white', anchor=W).grid(row=0, sticky=W)
        Label(scoreboard_frame, text="Trials completed:", bg='white', anchor=W).grid(row=2, sticky=W)
        Label(scoreboard_frame, text="Next trial:", bg='white', anchor=W).grid(row=4, sticky=W)
        Label(scoreboard_frame, text="Rail ends:", bg='white', anchor=W).grid(row=6, sticky=W)
        self.entry_end.grid(row=1, sticky=W)
        self.entry_trial_ct.grid(row=3, sticky=W)
        self.entry_nextTrial.grid(row=5, sticky=W)
        self.entry_rail_ends.grid(row=7, sticky=W)

        self.scoreboard_objs = [self.entry_end,
                                self.entry_trial_ct,
                                self.entry_nextTrial,
                                self.entry_rail_ends]
        
        ###### GUI OBJECTS ORGANIZED BY TIME ACTIVE ######
        # List of components to disable at open
        self.obj_to_disable_at_open = [self.option_ports,
                                       self.button_update_ports,
                                       self.button_open_port,
                                       self.entry_presession,
                                       self.entry_postsession,
                                       self.entry_csplus,
                                       self.entry_csminus,
                                       self.entry_trial_dur,
                                       self.entry_meanITI,
                                       self.entry_minITI,
                                       self.entry_maxITI,
                                       self.entry_csplus_dur,
                                       self.entry_csplus_freq,
                                       self.entry_csminus_dur,
                                       self.entry_csminus_freq,
                                       self.radio_uniform,
                                       self.radio_exp,
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
        self.button_close_port['state'] = DISABLED
        # self.entry_slack.insert(0, "@randall")
        self.entry_presession.insert(0, 30000)
        self.entry_postsession.insert(0, 0)
        self.entry_csplus.insert(0, 10)
        self.entry_csminus.insert(0, 0)
        self.entry_trial_dur.insert(0, 60000)
        self.distro_var.set(1)
        self.entry_meanITI.insert(0, 90000)
        self.entry_minITI.insert(0, 2000)
        self.entry_maxITI.insert(0, 20000)
        self.entry_minITI['state'] = DISABLED
        self.entry_maxITI['state'] = DISABLED
        self.entry_csplus_dur.insert(0, 3000)
        self.entry_csplus_freq.insert(0, 10000)
        self.entry_csminus_dur.insert(0, 3000)
        self.entry_csminus_freq.insert(0, 12000)
        self.image_var.set(1)
        self.print_var.set(True)
        self.button_start['state'] = DISABLED
        self.button_stop['state'] = DISABLED

        ###### SESSION VARIABLES ######
        self.parameters = collections.OrderedDict()
        self.ser = serial.Serial(timeout=1, baudrate=9600)
        self.start_time = ""
        self.trial_onset = np.empty(0)
        self.track = np.empty(0)
        self.rail_end = np.empty(0)
        self.counter = {}
        self.in_trial = False
        self.trial_events = np.array([[]])
        self.trial_events_num = 0
        self.trial_events_count = 0
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
        if self.port_var.get() == "No ports found":
            tkMessageBox.showerror("Serial error", "No port selected. Make sure Arduino is plugged in.")
            print "No ports found. Please attach Arduino or check connection."
            self.gui_util('close')
            return

        # Define parameters
        # NOTE: Order is important here since this order is preserved when sending via serial.
        self.parameters['csplus_number'] = int(self.entry_csplus.get())
        self.parameters['csminus_number'] = int(self.entry_csminus.get())
        self.parameters['presession_window'] = int(self.entry_presession.get())
        self.parameters['postsession_window'] = int(self.entry_postsession.get())
        self.parameters['trial_duration'] = int(self.entry_trial_dur.get())
        self.parameters['uniform_distro'] = int(self.distro_var.get())
        self.parameters['mean_ITI'] = int(self.entry_meanITI.get())
        self.parameters['min_ITI'] = int(self.entry_minITI.get())
        self.parameters['max_ITI'] = int(self.entry_maxITI.get())
        self.parameters['csplus_duration'] = int(self.entry_csplus_dur.get())
        self.parameters['csplus_frequency'] = int(self.entry_csplus_freq.get())
        self.parameters['csminus_duration'] = int(self.entry_csminus_dur.get())
        self.parameters['csminus_frequency'] = int(self.entry_csminus_freq.get())
        self.parameters['image_all'] = int(self.image_var.get())
        self.parameters['track_period'] = 50

        trial_num = self.parameters['csplus_number'] + self.parameters['csminus_number']
        trial_window = self.parameters['trial_duration']

        # Checkpoint #2
        # - Minimum ITI > trial length
        # - Mean ITI > trial length
        if (not self.parameters['uniform_distro']) &\
           (trial_window > self.parameters['min_ITI']):
            tkMessageBox.showerror("Parameter timing error.",
                                   "Minimum ITI is shorter than trial window. Trials will overlap.")
            return
        if trial_window > self.parameters['mean_ITI']:
            tkMessageBox.showerror("Parameter timing error.",
                                   "Mean ITI is shorter than trial window. Trials will overlap.")
            return

        # Clear old data
        # self.scatter_trial_csplus.set_offsets([])
        # self.scatter_trial_csminus.set_offsets([])
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
        self.ax_histo.set_xlim(0, trial_window)
        self.ax_raster.set_ylim(trial_num, 0)
        self.ax_raster.set_xlim(0, trial_window)
        
        # Create "blank" LineCollection to be filled later
        blank_segments = [np.array([[-1, yi], [-1, yi+1]]) for yi in np.arange(trial_num) \
                                                           for _ in np.arange(self.num_rail_segments)]
        self.raster_steps.set_segments(blank_segments)
        
        # Initialize/clear old data
        self.trial_onset = np.zeros(trial_num, dtype='uint32')
        self.steps = np.zeros((2, 360000), dtype='uint32')
        self.steps_by_trial = np.zeros(trial_num, dtype='uint32')
        self.track = np.zeros((2, 360000), dtype='int32')
        self.rail_end = np.zeros(trial_num, dtype='uint32')
        self.counter = {'trial': -1,
                        'track': 0,
                        'steps': 0}

        # Variables for trial histogram
        self.in_trial = False
        
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

        slack_test(self.entry_slack.get(), None)
        
        # Run session
        self.ser.flushInput()            # Remove data from serial input
        self.ser.write('E')
        self.start_time = datetime.now().strftime("%H:%M:%S")
        print "Session started at about " + self.start_time

        # Create thread to scan serial
        thread_scan = threading.Thread(target=scan_serial,
                                       args=(self.q, self.ser, self.parameters, self.print_var.get()))
        thread_scan.start()

        # Update GUI alongside scan_serial
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
        code_next_trial = 3
        code_trial_onset_csplus = 4
        code_trial_onset_csminus = 5
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
                self.steps_by_trial[self.counter['trial']] += dist

                ##### PLEASE CHECK THIS #####
                trial_start_ix = self.counter['trial'] * self.num_rail_segments
                trial_stop_ix = (self.counter['trial'] + 1) * self.num_rail_segments
                segments = self.raster_steps.get_segments()
                trial_line_segments = segments[trial_start_ix:trial_stop_ix]
                rail_milestones_ahead = [segment[0, 0] < 0 for segment in trial_line_segments]  # rail segments to be passed (milestones)
                rail_milestones_new = (self.steps_by_trial[self.counter['trial']] > rail_milestones) & \
                                      rail_milestones_ahead
                if np.any(rail_milestones_new):
                    for nn, xx in enumerate(rail_milestones_new):
                        if xx:
                            trial_line_segments[nn][:, 0] = ts
                    # trial_line_segments[rail_milestones_new], :, 0] = ts
                    self.raster_steps.set_segments(segments)
                    self.plot_canvas.draw()
                #############################

                # Increment counter
                self.counter['steps'] += 1

            elif code == code_rail_end:
                # Record time end of rail reached
                self.rail_end[self.counter['trial']] = ts

                # Update scoreboard
                self.entry_rail_ends.delete(0, END)
                self.entry_rail_ends.insert(0, np.count_nonzero(self.rail_end))
                
                # Create data to plot in raster
                # Data includes 3rd point that is NaN to "disconnect" tick marks from neighboring ones.
                trial_ts = ts - self.trial_onset[self.counter['trial']]
                new_data = np.append(self.raster_rail_end[0].get_data(),
                                     [[trial_ts] * 3, np.array([0, 1, np.nan]) + self.counter['trial']],
                                     axis=1)
                self.raster_rail_end[0].set_data(new_data)
                self.plot_canvas.draw()

            elif code == code_next_trial:
                # Timestamp of next trial
                # Received at the the end of the previous trial *AND* at the beginning of session.
                self.in_trial = False
                self.counter['trial'] += 1          # Since executed at the beginning of session, value was initialized at -1
                self.entry_trial_ct.delete(0, END)
                self.entry_trial_ct.insert(0, self.counter['trial'])

                # On last trial, ts == 0
                if ts:
                    next_trial = datetime.now() + timedelta(seconds=ts/1000)
                    self.entry_nextTrial.delete(0, END)
                    self.entry_nextTrial.insert(0, next_trial.strftime("%H:%M:%S"))
                else:
                    self.entry_nextTrial.delete(0, END)
                    self.entry_nextTrial.insert(0, "-")

            elif code in [code_trial_onset_csplus, code_trial_onset_csminus]:
                trial_dur = self.parameters['trial_duration']

                # Timestamp of trial start
                self.in_trial = True

                # Record time
                self.trial_onset[self.counter['trial']] = ts
                
                # Update trial progress bar
                if code == code_trial_onset_csplus:
                    trial_color = self.color_csplus
                else:
                    trial_color = self.color_csminus
                self.ax_total.axvspan(ts, ts + trial_dur,
                                      facecolor=trial_color, edgecolor='none')
                self.plot_canvas.draw()

                # Do NOT increment counter until end of trial
                # self.counter['trial'] += 1

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

                # NEW ###############################################################
                # Update raster plot
                track_bnd = 15
                if self.in_trial:
                    trial_ts = ts - self.trial_onset[self.counter['trial']]
                    # Update raster plot here #
                
                # Increment counter
                self.counter['track'] += 1

        self.parent.after(refresh_rate, self.update_session, data_file)

    def stop_session(self, data_file):
        self.gui_util('stop')
        self.close_serial()
        end_time = datetime.now().strftime("%H:%M:%S")

        if data_file:
            behav_grp = data_file.create_group('behavior')
            behav_grp.create_dataset(name='trial_onset', data=self.trial_onset, dtype='uint32')
            behav_grp.create_dataset(name='steps', data=self.steps[:, :self.counter['steps']], dtype='uint32')
            behav_grp.create_dataset(name='steps_by_trial', data=self.steps_by_trial, dtype='uint32')
            behav_grp.create_dataset(name='track', data=self.track[:, :self.counter['track']], dtype='int32')
            behav_grp.create_dataset(name='rail_end', data=self.rail_end, dtype='uint32')

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
        if self.entry_slack.get():
            slack.chat.post_message(self.entry_slack.get(), "Session ended.")


def slack_test(slack_recipient, msg):
    # Creates Slack message to slack_recipient from Bot. Message is string msg.

    # Verify Slack recipient
    if not slack_recipient:
        return
    slack_code = slack_recipient[0]
    slack_name = slack_recipient[1::]
    if slack_code is '@':
        slack_users = slack.users.list().body['members']
        slack_user_names = [user['name'] for user in slack_users]
        if slack_name not in slack_user_names:
            tkMessageBox.showerror("Slack error", "Slack user does not exist")
    elif slack_code is '#':
        slack_channels = slack.channels.list().body['members']
        slack_channel_names = [channel['name'] for channel in slack_channels]
        if slack_name not in slack_channel_names:
            tkMessageBox.showerror("Slack error", "Slack channel does not exist")
    else:
        tkMessageBox.showerror("Slack error", "Slack recipient is invalid.")

    if msg:
        slack.chat.post_message(slack_recipient, msg)


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
