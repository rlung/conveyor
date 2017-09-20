#!/usr/bin/env python

"""
Odor presentation

Creates GUI to control behavioral and imaging devices for in vivo calcium
imaging. Script interfaces with Arduino microcontroller and imaging devices.
"""
# import os
# if os.name == 'nt':
import matplotlib
matplotlib.use('TKAgg')
import Tkinter as tk
import tkMessageBox
import tkFileDialog
from ScrolledText import ScrolledText
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
# import matplotlib.pyplot as plt
from matplotlib.figure import Figure
import matplotlib.animation as animation
from matplotlib.colors import LinearSegmentedColormap
from matplotlib import style
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2TkAgg
import seaborn as sns
# from PIL import Image, ImageTk
from instrumental import instrument, list_instruments
import pdb


# Setup Slack
# Token is stored in text file defined by 'key_file'
key_file = os.path.join(os.path.expanduser('~'), '.slack')
if os.path.isfile(key_file):
    with open(key_file, 'r') as kf:
        slack = Slacker(kf.read())
else:
    slack = None

history = 10000
# subsamp = {1: 1,
#            2: 2,
#            3: 4,
#            4: 8}


def record(q_in, q_out, ts,
           cam, frames,
           frame_dur, session_length):
    
    # Grabs frames from `cam` object.

    print("Recording...")
    start_time = time.clock()
    nframes = len(ts)

    f = 0
    while (time.clock() - start_time < session_length and
           f < nframes):

        # Look for stop signal
        if not q_in.empty():
            if q_in.get() == 0:
                print("Camera recording stopped: {}".format(time.clock() - start_time))
                q_out.put(f)
                return

        # Wait for start of next frame
        # while time.clock() < next_frame:
        #     pass
        cam.wait_for_frame()

        # Record frame and timestamp
        ts[f] = (time.clock() - start_time) * 1000
        frames[f, ...] = cam.latest_frame()
        
        # Increment timer/counter
        # next_frame += frame_dur
        f += 1

    print("Recording limit reached: {}".format(time.clock() - start_time))
    q_out.put(f)


class InputManager(tk.Frame):

    def __init__(self, parent):
        tk.Frame.__init__(self, parent)

        # GUI layout
        # parent
        # - frame_parameter
        #   + session_frame
        #     ~ session_prop_frame
        #     ~ track_frame
        #   + hardware_frame
        #     ~ frame_preview
        #     ~ frame_cam
        #     ~ serial_frame
        #     ~ debug_frame
        #   + start_frame
        #   + slack_frame
        # - monitor_frame
        #   + (figure)
        #   + scoreboard_frame

        entry_width = 10
        ew = 10  # Width of Entry UI
        px = 15
        py = 5
        px1 = 5
        py1 = 2

        self.parent = parent
        parent.columnconfigure(0, weight=1)

        ###########################
        ##### PARAMETER FRAME #####
        ###########################
        frame_parameter = tk.Frame(parent)
        frame_parameter.grid(row=0, column=0)
        frame_parameter.grid_columnconfigure(0, weight=1)
        frame_parameter.grid_columnconfigure(1, weight=1)
        frame_parameter.grid_columnconfigure(2, weight=1)

        # Session parameters frame
        session_frame = tk.Frame(frame_parameter)
        session_frame.grid(row=0, column=0, padx=15, pady=5)
        session_frame.columnconfigure(0, weight=1)

        ## Camera preview
        self.frame_preview = tk.Frame(session_frame)
        self.frame_preview.grid(row=0, column=0, sticky='wens')

        # self.fig_preview, self.ax_preview = plt.subplots(figsize=(1280./1024 * 2.5, 2.5))
        self.fig_preview = Figure(figsize=(1280./1024 * 2.5, 2.5))
        self.ax_preview = self.fig_preview.add_axes([0, 0, 1, 1])
        self.fig_preview.subplots_adjust(left=0, bottom=0, right=1, top=1, wspace=0, hspace=0)
        self.im = self.ax_preview.imshow(np.zeros((1024, 1280)), vmin=1, vmax=254, cmap='gray', interpolation='none')
        self.im.cmap.set_under('b')
        self.im.cmap.set_over('r')
        self.ax_preview.axis('image')
        self.ax_preview.axis('off')
        self.canvas_preview = FigureCanvasTkAgg(self.fig_preview, self.frame_preview)
        self.canvas_preview.show()
        self.canvas_preview.draw()
        self.canvas_preview.get_tk_widget().grid(row=0, column=0, sticky='wens')

        ## UI for trial control
        session_prop_frame = tk.Frame(session_frame)
        session_prop_frame.grid(row=1, column=0, sticky='e', padx=15, pady=5)

        self.entry_session_dur = tk.Entry(session_prop_frame, width=entry_width)
        self.entry_trial_dur = tk.Entry(session_prop_frame, width=entry_width)
        tk.Label(session_prop_frame, text="Session duration: ", anchor=tk.E).grid(row=0, column=0, sticky=tk.E)
        tk.Label(session_prop_frame, text="Trial duration: ", anchor=tk.E).grid(row=1, column=0, sticky=tk.E)
        self.entry_session_dur.grid(row=0, column=1, sticky=tk.W)
        self.entry_trial_dur.grid(row=1, column=1, sticky=tk.W)

        ## UI for tracking
        track_frame = tk.Frame(session_frame)
        track_frame.grid(row=2, column=0, sticky='e', padx=15, pady=5)
        self.entry_track_period = tk.Entry(track_frame, width=entry_width)
        self.entry_track_steps = tk.Entry(track_frame, width=entry_width)
        tk.Label(track_frame, text="Track period (ms): ", anchor=tk.E).grid(row=0, column=0, sticky=tk.E)
        tk.Label(track_frame, text="Track steps: ", anchor=tk.E).grid(row=1, column=0, sticky=tk.E)
        self.entry_track_period.grid(row=0, column=1, sticky=tk.W)
        self.entry_track_steps.grid(row=1, column=1, sticky=tk.W)
        
        # # Options frame
        # opt_session_frame = tk.Frame(frame_parameter)
        # opt_session_frame.grid(row=0, column=0)

        # conveyor_frame = tk.LabelFrame(opt_session_frame, text="Conveyor")
        # conveyor_frame.grid(row=0, column=0, padx=10, pady=5, sticky=tk.W+tk.E)
        # self.conveyor_away_var = tk.BooleanVar()
        # self.check_conveyor_away = tk.Checkbutton(
        #     conveyor_frame,
        #     text="Set conveyor away",
        #     variable=self.conveyor_away_var)
        # self.check_conveyor_away.grid(row=0, column=0)

        # Hardware parameters
        hardware_frame = tk.Frame(frame_parameter)
        hardware_frame.grid(row=0, column=1)
        hardware_frame.grid_columnconfigure(0, weight=1)

        ## UI for camera
        self.frame_cam = tk.LabelFrame(hardware_frame, text="Camera")
        self.frame_cam.grid(row=0, column=0, padx=px, pady=py, sticky='we')

        self.var_preview = tk.BooleanVar()
        self.var_fps = tk.DoubleVar()
        self.var_vsub = tk.IntVar()
        self.var_hsub = tk.IntVar()
        self.var_gain = tk.IntVar()
        self.var_expo = tk.IntVar()
        self.var_instr = tk.StringVar()

        self.option_instr = tk.OptionMenu(self.frame_cam,
            self.var_instr, [])
        self.option_instr.configure(anchor=tk.W)
        self.button_refresh_instr = tk.Button(self.frame_cam,
            text="Update", command=self.update_instruments)
        self.button_preview = tk.Button(self.frame_cam,
            text="Preview", command=self.cam_preview)
        self.button_settings = tk.Button(self.frame_cam,
            text="Settings", command=self.cam_settings)

        self.option_instr.grid(row=1, column=0, columnspan=3, padx=px1, pady=py1, sticky='we')
        self.button_refresh_instr.grid(row=2, column=0, padx=px1, pady=py1, sticky='we')
        self.button_preview.grid(row=2, column=1, padx=px1, pady=py1, sticky='we')
        self.button_settings.grid(row=2, column=2, padx=px1, pady=py1, sticky='we')
        self.instrument_panels = [
            self.option_instr,
            self.button_refresh_instr,
        ]

        ## UI for Arduino
        serial_frame = tk.LabelFrame(hardware_frame, text="Arduino")
        serial_frame.grid(row=1, column=0, padx=px, pady=py, sticky='we')

        self.port_var = tk.StringVar()

        ###
        serial_ports_frame = tk.Frame(serial_frame)
        serial_ports_frame.grid(row=0, column=0, columnspan=2, sticky=tk.W)

        tk.Label(serial_ports_frame, text="Serial port:").grid(row=0, column=0, sticky=tk.E, padx=5)
        self.option_ports = tk.OptionMenu(serial_ports_frame, self.port_var, [])
        self.option_ports.grid(row=0, column=1, sticky=tk.W+tk.E, padx=5)
        tk.Label(serial_ports_frame, text="Serial status:").grid(row=1, column=0, sticky=tk.E, padx=5)
        self.entry_serial_status = tk.Entry(serial_ports_frame)

        self.entry_serial_status.grid(row=1, column=1, sticky=tk.W, padx=5)
        self.entry_serial_status.insert(0, 'Closed')

        self.entry_serial_status['state'] = 'normal'
        self.entry_serial_status['state'] = 'readonly'

        ###
        open_close_frame = tk.Frame(serial_frame)
        open_close_frame.grid(row=1, column=0, columnspan=2, pady=10)

        self.button_open_port = tk.Button(open_close_frame, text="Open", command=self.open_serial)
        self.button_close_port = tk.Button(open_close_frame, text="Close", command=self.close_serial)
        self.button_update_ports = tk.Button(open_close_frame, text="Update", command=self.update_ports)

        self.button_open_port.grid(row=0, column=0, pady=5)
        self.button_close_port.grid(row=0, column=1, padx=10, pady=5)
        self.button_update_ports.grid(row=0, column=2, pady=5)

        ## UI for debug options
        debug_frame = tk.LabelFrame(hardware_frame, text="Debugging")
        debug_frame.grid(row=2, column=0, padx=px, pady=py, sticky='we')
        
        self.print_var = tk.BooleanVar()
        self.var_sim_cam = tk.BooleanVar()
        self.var_sim_arduino = tk.BooleanVar()

        self.check_print = tk.Checkbutton(debug_frame, text=" Print Arduino output", variable=self.print_var)
        self.check_sim_cam = tk.Checkbutton(debug_frame, text=" Simulate camera", variable=self.var_sim_cam)
        self.check_sim_arduino = tk.Checkbutton(debug_frame, text=" Simulate Arduino", variable=self.var_sim_arduino)
        self.pdb = tk.Button(debug_frame, text="pdb", command=pdb.set_trace)

        self.check_print.grid(row=0, column=0, padx=px1, sticky='w')
        self.check_sim_cam.grid(row=1, column=0, padx=px1, sticky='w')
        self.check_sim_arduino.grid(row=2, column=0, padx=px1, sticky='w')
        self.pdb.grid(row=3, column=0, padx=px1, sticky='w')

        # Frame for file
        frame_file = tk.Frame(frame_parameter)
        frame_file.grid(row=0, column=2, padx=5, pady=5, sticky='wens')
        frame_file.columnconfigure(0, weight=1)

        ## Notes
        frame_notes = tk.Frame(frame_file)
        frame_notes.grid(row=0, sticky='wens', padx=px, pady=py)
        frame_notes.grid_columnconfigure(0, weight=1)

        tk.Label(frame_notes, text="Notes:").grid(row=0, column=0, sticky='w')
        self.scrolled_notes = ScrolledText(frame_notes, width=20, height=15)

        self.scrolled_notes.grid(row=1, column=0, sticky='wens')

        ## Slack
        frame_slack = tk.Frame(frame_file)
        frame_slack.grid(row=1, sticky='we', padx=px, pady=py)
        frame_slack.grid_columnconfigure(0, weight=3)
        frame_slack.grid_columnconfigure(1, weight=1)

        tk.Label(frame_slack, text="Slack address: ", anchor='w').grid(row=0, column=0, sticky='we')
        self.entry_slack = tk.Entry(frame_slack)
        self.button_slack = tk.Button(frame_slack, text="", command=lambda: slack_msg(self.entry_slack.get(), "Test", test=True))

        self.entry_slack.grid(row=1, column=0, sticky='wens')
        self.button_slack.grid(row=1, column=1, sticky='e')

        ## Start frame
        start_frame = tk.Frame(frame_file)
        start_frame.grid(row=2, column=0, columnspan=2, padx=px, pady=py, sticky='we')
        start_frame.columnconfigure(0, weight=1)
        start_frame.columnconfigure(1, weight=1)
        start_frame.columnconfigure(2, weight=1)
        start_frame.columnconfigure(3, weight=1)

        self.stop = tk.BooleanVar()
        self.stop.set(False)

        tk.Label(start_frame, text="File to save data:", anchor=tk.W).grid(row=0, column=0, columnspan=4, sticky=tk.W)
        self.entry_save = tk.Entry(start_frame)
        self.button_save_file = tk.Button(start_frame, text="...", command=self.get_save_file)
        self.button_start = tk.Button(start_frame, text="Start", command=lambda: self.parent.after(0, self.start))
        self.button_stop = tk.Button(start_frame, text="Stop", command=lambda: self.stop.set(True))

        self.entry_save.grid(row=1, column=0, columnspan=3, sticky='wens')
        self.button_save_file.grid(row=1, column=4, sticky='e')
        self.button_start.grid(row=2, column=0, sticky='w')
        self.button_stop.grid(row=2, column=1, sticky='w')

        ###########################
        ###### MONITOR FRAME ######
        ###########################
        monitor_frame = tk.Frame(parent, bg='white')
        monitor_frame.grid(row=1, column=0, sticky=tk.W+tk.E+tk.N+tk.S)
        monitor_frame.columnconfigure(0, weight=4)

        ##### PLOTS #####
        self.num_rail_segments = 10  # Number of segments to split rail--for plotting
        trial_window = 30000

        sns.set_style('dark')
        self.color_vel = 'darkslategray'

        # self.fig, self.ax = plt.subplots(figsize=(8, 2))
        self.fig = Figure(figsize=(8, 2))
        self.ax = self.fig.add_subplot(1, 1, 1)
        self.ax.set_xlabel("Trial time (ms)")
        self.ax.set_ylabel("Relative velocity")
        self.ax.set_xlim(0, history)
        self.ax.set_ylim(-50, 50)
        self.vel_trace, = self.ax.plot([], [], c=self.color_vel)
        self.ax.axhline(y=0, linestyle='--', linewidth=1, color='0.5')

        self.plot_canvas = FigureCanvasTkAgg(self.fig, monitor_frame)
        self.fig.tight_layout()
        self.plot_canvas.show()
        self.plot_canvas.draw()
        self.plot_canvas.get_tk_widget().grid(row=0, column=0, rowspan=2, sticky=tk.W+tk.E+tk.N+tk.S)

        ##### SCOREBOARD #####
        scoreboard_frame = tk.Frame(monitor_frame, bg='white')
        scoreboard_frame.grid(row=0, column=1, padx=20, sticky=tk.N)

        self.manual = tk.BooleanVar()
        self.entry_start = tk.Entry(scoreboard_frame, width=entry_width)
        self.entry_end = tk.Entry(scoreboard_frame, width=entry_width)
        self.button_manual = tk.Button(scoreboard_frame, command=lambda: self.manual.set(True))
        tk.Label(scoreboard_frame, text="Session start:", bg='white', anchor=tk.W).grid(row=0, sticky=tk.W)
        tk.Label(scoreboard_frame, text="Session end:", bg='white', anchor=tk.W).grid(row=2, sticky=tk.W)
        self.entry_start.grid(row=1, sticky=tk.W)
        self.entry_end.grid(row=3, sticky=tk.W)
        self.button_manual.grid(row=4, sticky=tk.W+tk.E)

        self.scoreboard_objs = [
            self.entry_start,
            self.entry_end
        ]
        
        ###### GUI OBJECTS ORGANIZED BY TIME ACTIVE ######
        # List of components to disable at open
        self.obj_to_disable_at_open = [
            self.option_ports,
            self.button_update_ports,
            self.button_open_port,
            self.entry_session_dur,
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
        self.update_instruments()

        # Default values
        self.entry_session_dur.insert(0, 60000)
        self.entry_trial_dur.insert(0, 5000)
        self.entry_track_period.insert(0, 50)
        self.entry_track_steps.insert(0, 5)
        self.print_var.set(True)
        self.button_close_port['state'] = 'disabled'
        self.button_start['state'] = 'disabled'
        self.button_stop['state'] = 'disabled'
        self.var_fps.set(10)
        self.var_vsub.set(50)
        self.var_hsub.set(50)
        self.var_gain.set(15)
        self.var_expo.set(40)

        ###### SESSION VARIABLES ######
        self.cam = None
        self.scale_fps = None
        self.parameters = collections.OrderedDict()
        self.ser = serial.Serial(timeout=1, baudrate=9600)
        self.start_time = ""
        self.counter = {}
        self.q = Queue()
        self.q_to_thread_rec = Queue()
        self.q_from_thread_rec = Queue()
        self.gui_update_ct = 0  # count number of times GUI has been updated

    def update_instruments(self):
        self.instrs = {}
        instrs = list_instruments()
        menu = self.option_instr['menu']
        menu.delete(0, tk.END)
        if instrs:
            for instr in instrs:
                menu.add_command(label=instr.name, command=lambda x=instr.name: self.var_instr.set(x))
                self.instrs[instr.name] = instr
            self.var_instr.set(instrs[0].name)
        else:
            self.var_instr.set("No instruments found")
            self.instrs = {}

    def cam_start(self):
        # if not self.cam:
        #     instrs = list_instruments()
        #     instr = [x for x in instrs if x.name == self.var_instr.get()]
        #     if instr:
        #         self.cam = instrument(instr[0])
        #     else:
        #         return 1

        if not self.cam:
            cam_name = self.var_instr.get()
            if cam_name:
                self.cam = instrument(self.instrs[cam_name])
            else:
                print("No camera selected.")
                return 1

        aoi_dy = 2
        aoi_dx = 4
        dim_y, dim_x = (1024, 1280)
        dy = self.var_vsub.get() * aoi_dy
        dx = self.var_hsub.get() * aoi_dx
        fps = self.var_fps.get()
        expo = self.var_expo.get()
        exposure_time = (1000. / fps) * (expo / 100.)

        self.cam.start_live_video(
            framerate='{}Hz'.format(fps),
            # vsub=int(self.var_vsub.get()),
            # hsub=int(self.var_hsub.get()),
            top=dy,
            bot=dim_y - dy,
            left=dx,
            right=dim_x - dx,
            gain=self.var_gain.get(),
            exposure_time='{}ms'.format(exposure_time)
        )

        self.var_fps.set(self.cam.framerate)
        if self.scale_fps:
            self.scale_fps.set(self.cam.framerate)

        # instrs = list_instruments()
        # instr = [x for x in instrs if x.name == self.var_instr.get()]
        # if instr:
        #     self.cam = instrument(instr[0])
        #     self.var_cam_state.set(True)
        #     # self.cam.start_live
        # else:
        #     return 1

    def cam_close(self):
        if self.cam:
            print("Closing camera")
            self.cam.close()
            self.cam = None

    # TODO: need to limit scale to step size and range of camera
    # def scale(self, dim):
    #     pdb.set_trace()

    #     if dim == 'x':
    #         slider = self.scale_hsub
    #         slider_var = self.var_hsub
    #     elif dim == 'y':
    #         slider = self.scale_vsub
    #         slider_var = self.var_vsub

    #     old_val = slider.get()
    #     new_val = step_size * np.round(old_val / step_size)

    #     slider.set(new_val)
    #     slider_var.set(new_val)

    def cam_settings(self):
        px = 15
        py = 5

        dy, dx = (1024, 1280)
        aoi_x = 624
        aoi_y = 510
        aoi_dx = 4
        aoi_dy = 2

        window_settings = tk.Toplevel(self)
        window_settings.wm_title("Camera settings")

        frame_settings = tk.Frame(window_settings)
        frame_settings.grid()

        tk.Label(frame_settings, text="FPS: ", anchor='e').grid(row=1, column=0, sticky='e')
        tk.Label(frame_settings, text="Vertical subsampling: ", anchor='e').grid(row=2, column=0, sticky='e')
        tk.Label(frame_settings, text="Horizontal subsampling: ", anchor='e').grid(row=3, column=0, sticky='e')
        tk.Label(frame_settings, text="Gain: ", anchor='e').grid(row=4, column=0, sticky='e')
        tk.Label(frame_settings, text="Exposure (% of frame): ", anchor='e').grid(row=5, column=0, sticky='e')
        self.scale_fps = tk.Scale(frame_settings, orient='horizontal', from_=1, to=60,
            command=self.var_fps.set, resolution=0.01)
        scale_vsub = tk.Scale(frame_settings, orient='horizontal', from_=0, to=aoi_y / aoi_dy,
            command=self.var_vsub.set)
        scale_hsub = tk.Scale(frame_settings, orient='horizontal', from_=0, to=aoi_x / aoi_dx,
            command=self.var_hsub.set)
        scale_gain = tk.Scale(frame_settings, orient='horizontal', from_=0, to=100,
            command=self.var_gain.set)
        scale_expo = tk.Scale(frame_settings, orient='horizontal', from_=1, to=100,
            command=self.var_expo.set)
        self.scale_fps.set(self.var_fps.get())
        scale_vsub.set(self.var_vsub.get())
        scale_hsub.set(self.var_hsub.get())
        scale_gain.set(self.var_gain.get())
        scale_expo.set(self.var_expo.get())
        button_update = tk.Button(frame_settings, text="Update preview",
            command=self.cam_start)

        self.scale_fps.grid(row=1, column=1, sticky='we')
        scale_vsub.grid(row=2, column=1, sticky='we')
        scale_hsub.grid(row=3, column=1, sticky='we')
        scale_gain.grid(row=4, column=1, sticky='we')
        scale_expo.grid(row=5, column=1, sticky='we')
        button_update.grid(row=6, column=0, columnspan=2, padx=px, pady=py, sticky='we')

        def close_protocol():
            window_settings.destroy()
            self.scale_fps = None

        window_settings.protocol('WM_DELETE_WINDOW', close_protocol)
        window_settings.transient(self)
        window_settings.grab_set()

    def cam_preview(self):
        # Toggle preview on or off
        # Depends on state of `self.var_preview`
        
        if not self.var_preview.get():
            self.var_preview.set(True)
            self.button_preview['foreground'] = 'blue'
            self.cam_preview_update()
        else:
            self.var_preview.set(False)
            self.button_preview['foreground'] = 'black'
            self.cam_close()

    def cam_preview_update(self):
        # Check if preview mode is still active
        if not self.var_preview.get():
            return

        # Turn on camera
        if not self.cam:
            state = self.cam_start()
            if state:
                print("Unable to start camera")
                return

        # Get frame
        im = self.cam.latest_frame()
        self.im.set_data(im)
        self.canvas_preview.draw_idle()

        # if not self.var_cam_state.get():
        #     state = self.cam_start()
        #     if state:
        #         print("Unable to start camera")
        #         return

        # start_time = time.clock()
        # frame_dur = 1000. / self.var_fps.get()

        # exposure_time = frame_dur * self.var_expo.get()/100.
        # im = self.cam.grab_image(
        #     vsub=subsamp[self.var_vsub.get()],
        #     hsub=subsamp[self.var_hsub.get()],
        #     gain=self.var_gain.get(),
        #     exposure_time='{}ms'.format(exposure_time))
        # too_fast = True if time.clock() - start_time > frame_dur / 1000. else False
        # self.im.set_data(im)
        # # self.ax_preview.set_ylim(0, self.cam.height)
        # # self.ax_preview.set_xlim(0, self.cam.width)
        # self.ax_preview.draw_artist(self.im)
        # self.fig_preview.canvas.blit(self.ax_preview.bbox)

        self.parent.after(20, self.cam_preview_update)


    def update_ports(self):
        ports_info = list(serial.tools.list_ports.comports())
        ports = [port.device for port in ports_info]
        ports_description = [port.description for port in ports_info]

        menu = self.option_ports['menu']
        menu.delete(0, tk.END)
        if ports:
            for port, description in zip(ports, ports_description):
                menu.add_command(label=description, command=lambda com=port: self.port_var.set(com))
            self.port_var.set(ports[0])
        else:
            self.port_var.set("No ports found")

    def get_save_file(self):
        ''' Opens prompt for file for data to be saved
        Runs when button beside save file is pressed.
        '''

        save_file = tkFileDialog.asksaveasfilename(
            defaultextension=".h5",
            filetypes=[
                ("HDF5 file", "*.h5 *.hdf5"),
                ("All files", "*.*")
            ]
        )
        self.entry_save.delete(0, tk.END)
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

            self.entry_serial_status.config(state='normal', fg='red')
            self.entry_serial_status.delete(0, tk.END)
            self.entry_serial_status.insert(0, 'Opening...')
            self.entry_serial_status['state'] = 'readonly'

        elif option == 'opened':
            # Enable start objects
            for obj in self.obj_to_enable_at_open:
                obj['state'] = 'normal'

            self.entry_serial_status.config(state='normal', fg='black')
            self.entry_serial_status.delete(0, tk.END)
            self.entry_serial_status.insert(0, 'Opened')
            self.entry_serial_status['state'] = 'readonly'

        elif option == 'close':
            for obj, to_enable in zip(self.obj_to_disable_at_open, self.obj_enabled_at_open):
                if to_enable: obj['state'] = 'normal'         # NOT SURE IF THAT'S CORRECT
            for obj in self.obj_to_enable_at_open:
                obj['state'] = 'disabled'

            self.entry_serial_status.config(state='normal', fg='black')
            self.entry_serial_status.delete(0, tk.END)
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

            self.entry_serial_status.config(state='normal', fg='black')
            self.entry_serial_status.delete(0, tk.END)
            self.entry_serial_status.insert(0, 'Closed')
            self.entry_serial_status['state'] = 'readonly'

    def open_serial(self):
        ''' Open serial connection to Arduino
        Executes when "Open" is pressed
        '''

        # Disable GUI components
        self.gui_util('open')

        # Define parameters
        # NOTE: Order is important here since this order is preserved when sending via serial.
        self.parameters['session_duration'] = int(self.entry_session_dur.get())
        self.parameters['trial_duration'] = int(self.entry_trial_dur.get())
        self.parameters['track_period'] = int(self.entry_track_period.get())
        self.parameters['track_steps'] = int(self.entry_track_steps.get())

        # Clear old data
        self.vel_trace.set_data([[], []])
        # self.ax.set_xlim(0, self.parameters['trial_duration'])
        self.plot_canvas.draw()
        for obj in self.scoreboard_objs:
            obj.delete(0, tk.END)

        # Initialize/clear old data
        self.counter = {
            'trial': 0,
            'track': 0,
            'steps': 0
        }

        # Open serial and upload to Arduino
        self.ser.port = self.port_var.get()
        ser_return = start_arduino(self.ser, self.parameters)

        if ser_return:
            tkMessageBox.showerror("Serial error",
                                   "{}: {}\n\nCould not create serial connection."\
                                   .format(ser_return.errno, ser_return.strerror))
            print "\n{}: {}\nCould not create serial connection. Check port is open."\
                  .format(ser_return.errno, ser_return.strerror)
            self.close_serial()
            self.gui_util('close')
            return

        self.gui_util('opened')
        print "Waiting for start command."
    
    def close_serial(self):
        ''' Close serial connection to Arduino '''

        self.ser.close()
        self.gui_util('close')
        print "Connection to Arduino closed."
    
    def start(self):
        self.gui_util('start')

        # Clear Queues
        for q in [self.q, self.q_to_thread_rec, self.q_from_thread_rec]:
            with q.mutex:
                q.queue.clear()

        session_length = self.parameters['session_duration']
        nstepframes = session_length / float(self.entry_track_period.get())

        # Start camera
        self.cam_start()
        dy = self.cam.height
        dx = self.cam.width
        fps = self.cam.framerate
        nframes = fps * session_length / 1000.
        frame_dur_s = 1. / fps
        exposure_time = frame_dur_s * self.var_expo.get() / 100.

        # Create data file
        if self.entry_save.get():
            try:
                # Create file if it doesn't already exist ('x' parameter)
                self.data_file = h5py.File(self.entry_save.get(), 'x')
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
            self.data_file = h5py.File(filename, 'x')

        self.grp_cam = self.data_file.create_group('cam')
        self.dset_ts = self.grp_cam.create_dataset('timestamps', dtype=float,
            shape=(int(nframes * 1.1), ), chunks=(1, ))
        self.dset_cam = self.grp_cam.create_dataset('frames', dtype='uint8',
            shape=(int(nframes * 1.1), dy, dx), chunks=(1, dy, dx))
        self.grp_cam.attrs['fps'] = fps
        self.grp_cam.attrs['exposure'] = exposure_time
        self.grp_cam.attrs['gain'] = self.var_gain.get()
        self.grp_cam.attrs['vsub'] = self.var_vsub.get()
        self.grp_cam.attrs['hsub'] = self.var_hsub.get()

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
            args=(self.q, self.q_to_thread_rec, self.ser, self.parameters, self.print_var.get()))

        # Create thread to record from camera
        thread_rec = threading.Thread(
            target=record,
            args=(
                self.q_to_thread_rec, self.q_from_thread_rec, self.dset_ts,
                self.cam, self.dset_cam,
                frame_dur_s, session_length)
        )

        # frame_dur_s = 1. / fps
        # exposure_time = frame_dur_s * 1000 * self.var_expo.get()/100.
        # thread_rec = threading.Thread(
        #     target=record,
        #     args=(
        #         self.q_to_thread_rec, self.q_from_thread_rec, self.ts,
        #         self.regcam, self.reg_dset,
        #         self.var_vsub.get(), self.var_hsub.get(), self.var_gain.get(), exposure_time,
        #         frame_dur_s, session_length
        #     )
        # )

        # Run session
        start_time = datetime.now()
        approx_end = start_time + timedelta(milliseconds=self.parameters['session_duration'])
        self.start_time = start_time.strftime("%H:%M:%S")
        print("Session start ~ {}".format(self.start_time))
        self.entry_start.insert(0, self.start_time)
        self.entry_end.insert(0, '~' + approx_end.strftime("%H:%M:%S"))
        self.behav_grp.attrs['start_time'] = self.start_time

        self.ser.flushInput()                                   # Remove data from serial input
        self.ser.write('E')                                     # Start signal for Arduino
        thread_scan.start()
        thread_rec.start()

        # Update GUI
        self.update_session()

    def update_session(self):
        # Checks Queue for incoming data from arduino. Data arrives as comma-separated values with the first element
        # ('code') defining the type of data.

        refresh_rate = 10  # Rate to update GUI. Should be faster than data coming in, eg tracking rate

        # Codes
        code_end = 0
        code_steps = 1
        code_trial_start = 3
        code_trial_man = 4
        code_rail_leave = 5
        code_rail_home = 6
        code_track = 7

        # End on "Stop" button (by user)
        if self.stop.get():
            self.stop.set(False)
            self.ser.write("0")
            print("User triggered stop.")
        elif self.manual.get():
            self.manual.set(False)
            self.ser.write("F")
            print("Manual trial triggered")

        # Incoming queue has format:
        #   [code, ts [, extra values...]]
        if not self.q.empty():
            q_in = self.q.get()
            code = q_in[0]
            ts = q_in[1]

            # stop_session is called only when Arduino sends stop code
            if code == code_end:
                arduino_end = ts
                self.q_to_thread_rec.put(0)
                # while self.q_from_thread_rec.empty():
                #     pass
                print("Stopping session.")
                self.stop_session(self.q_from_thread_rec.get(), arduino_end)
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

                # # Update plot
                # x0 = ts - history
                # X, Y = self.vel_trace.get_data()
                # X = np.append(X, ts)
                # Y = np.append(Y, dist)
                # recent_pts = X >= x0

                # if any(recent_pts):
                #     X = X[recent_pts]
                #     Y = Y[recent_pts]

                #     self.vel_trace.set_data(X, Y)
                #     self.ax.set_xlim(x0, ts)

                #     # self.ax.draw_artist(self.vel_trace)
                #     # self.fig.canvas.blit(self.ax.bbox)
                #     # self.fig.canvas.show()
                #     self.fig.canvas.draw_idle()

                # Increment counter
                self.counter['track'] += 1

        # # Increment GUI update counter
        # self.gui_update_ct += 1
        
        # # Update plot every 0.5 s
        # if self.gui_update_ct % 5 == 0:
        #     self.plot_canvas.draw()

        self.parent.after(refresh_rate, self.update_session)

    def stop_session(self, frame_cutoff=None, arduino_end=None):
        end_time = datetime.now().strftime("%H:%M:%S")
        print "Session ended at " + end_time
        self.gui_util('stop')
        self.close_serial()
        self.cam_close()

        if self.data_file:
            print("Writing behavioral data")
            self.behav_grp.attrs['end_time'] = end_time
            self.behav_grp['trials'].resize((self.counter['trial'], ))
            self.behav_grp['trial_manual'].resize((self.counter['trial'], ))
            self.behav_grp['rail_leave'].resize((self.counter['trial'], ))
            self.behav_grp['rail_home'].resize((self.counter['trial'], ))
            self.behav_grp['steps'].resize((2, self.counter['steps']))
            self.behav_grp['track'].resize((2, self.counter['track']))
            self.behav_grp.attrs['notes'] = self.scrolled_notes.get(1.0, tk.END)
            self.behav_grp.attrs['arduino_end'] = arduino_end

            self.grp_cam.attrs['end_time'] = end_time
            if frame_cutoff:
                print("Trimming recording")
                self.grp_cam['timestamps'].resize((frame_cutoff, ))
                _, dy, dx = self.grp_cam['frames'].shape
                self.grp_cam['frames'].resize((frame_cutoff, dy, dx))

            # Close HDF5 file object
            print("Closing file")
            self.data_file.close()
        
        # Clear self.parameters
        self.parameters = collections.OrderedDict()

        print("All done!")

        # Slack that session is done.
        if (self.entry_slack.get() and \
            slack):
            slack_msg(self.entry_slack.get(), "Session ended.")


def slack_msg(slack_recipient, msg, test=False):
    # Creates Slack message to slack_recipient from Bot. Message is string msg.
    bot_username = "Odor conveyor bot"
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
    sys.stdout.write("Uploading parameters to Arduino: {}".format(values))
    sys.stdout.flush()
    
    try:
        ser.open()
    except serial.SerialException as err:
        sys.stdout.write("\nFailed to open connection.\n")
        return err

    # Wait for connection to Arduino
    timeout = 5
    timeout_count = 0
    while 1:
        if timeout_count >= timeout:
            sys.stdout.write(" Startup prompt not found.\n")
            sys.stdout.flush()
            return serial.SerialException("Startup prompt not found.")
        sys.stdout.write(".")
        sys.stdout.flush()
        if ser.read(): break
        timeout_count += 1

    # Write parameters to Arduino
    ser.flushInput()            # Remove opening message from serial
    ser.write('+'.join(str(s) for s in values))
    while 1:
        if timeout_count >= timeout:
            sys.stdout.write(" Start signal from Arduino timed out.\n")
            sys.stdout.flush()
            return serial.SerialException("Start signal from Arduino timed out.")
        sys.stdout.write(".")
        sys.stdout.flush()
        if ser.read(): break
    print "\nArduino updated."

    return 0


def scan_serial(q, q_to_rec_thread, ser, parameters, print_arduino=False):
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
                q_to_rec_thread.put(0)
                if print_arduino: print "  Scan complete."
                return


def main():
    # GUI
    root = tk.Tk()
    root.wm_title("Odor presentation")
    # if os.name == 'nt':
    #     root.iconbitmap(os.path.join(os.getcwd(), 'neuron.ico'))
    InputManager(root)
    root.grid()
    root.mainloop()


if __name__ == '__main__':
    main()
