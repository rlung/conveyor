#!/usr/bin/env python

"""
Odor presentation

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
        #       - track_frame
        #     ~ opt_session_frame
        #       - conveyor_frame
        #       - debug_frame
        #   + start_frame
        #   + serial_frame
        #   + slack_frame
        # - monitor_frame
        #   + (figure)
        #   + scoreboard_frame

        entry_width = 10

        self.parent = parent
        parent.columnconfigure(0, weight=1)

        ###########################
        ##### PARAMETER FRAME #####
        ###########################
        parameter_frame = Frame(parent)
        parameter_frame.grid(row=0, column=0)

        ###### SESSION SETTINGS FRAME ######
        session_frame = Frame(parameter_frame)
        session_frame.grid(row=0, column=0, rowspan=2, padx=15, pady=5)

        core_session_frame = Frame(session_frame)
        core_session_frame.grid(row=0, column=0)

        # Session frame
        session_prop_frame = Frame(core_session_frame)
        session_prop_frame.grid(row=0, column=0, sticky=E, padx=15, pady=5)
        self.entry_trial_dur = Entry(session_prop_frame, width=entry_width)
        Label(session_prop_frame, text="Trial duration: ", anchor=E).grid(row=0, column=0, sticky=E)
        self.entry_trial_dur.grid(row=0, column=1, sticky=W)

        # Track frame
        track_frame = Frame(core_session_frame)
        track_frame.grid(row=2, column=0, sticky=E, padx=15, pady=5)
        self.entry_track_period = Entry(track_frame, width=entry_width)
        Label(track_frame, text="Track period (ms): ", anchor=E).grid(row=0, column=0, sticky=E)
        self.entry_track_period.grid(row=0, column=1, sticky=W)
        
        # Optional settings frame
        opt_session_frame = Frame(session_frame)
        opt_session_frame.grid(row=0, column=1)

        conveyor_frame = LabelFrame(opt_session_frame, text="Conveyor")
        conveyor_frame.grid(row=0, column=0, padx=10, pady=5, sticky=W+E)
        self.conveyor_away_var = BooleanVar()
        self.check_conveyor_away = Checkbutton(
            conveyor_frame,
            text="Set conveyor away",
            variable=self.conveyor_away_var)
        self.check_conveyor_away.grid(row=0, column=0)

        debug_frame = LabelFrame(opt_session_frame, text="Debugging")
        debug_frame.grid(row=1, column=0, padx=10, pady=5, sticky=W+E)
        self.print_var = BooleanVar()
        self.check_print = Checkbutton(debug_frame, text="Print Arduino output", variable=self.print_var)
        self.check_print.grid(row=0, column=0)

        ###### SERIAL FRAME ######
        serial_frame = Frame(parameter_frame)
        serial_frame.grid(row=0, column=1, padx=5, pady=5, sticky=W+E)
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
        slack_frame.grid(row=1, column=1, padx=5, pady=5, sticky=W+E)
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

        ##### PLOTS #####
        self.num_rail_segments = 10  # Number of segments to split rail--for plotting
        trial_window = 30000

        sns.set_style('dark')
        self.color_vel = 'darkslategray'

        self.fig, self.ax = plt.subplots(figsize=(8, 3))
        self.ax.set_xlabel("Trial time (ms)")
        self.ax.set_ylabel("Relative velocity")
        self.ax.set_xlim(0, 60000)
        self.ax.set_ylim(-50, 50)
        self.vel_trace, = self.ax.plot([], [], c=self.color_vel)
        self.ax.axhline(y=0, linestyle='--', linewidth=1, color='0.5')

        self.plot_canvas = FigureCanvasTkAgg(self.fig, monitor_frame)
        self.fig.tight_layout()
        self.plot_canvas.show()
        self.plot_canvas.get_tk_widget().grid(row=0, column=0, rowspan=2, sticky=W+E+N+S)

        ##### SCOREBOARD #####
        scoreboard_frame = Frame(monitor_frame, bg='white')
        scoreboard_frame.grid(row=0, column=1, padx=20, sticky=N)
        self.entry_start = Entry(scoreboard_frame, width=entry_width)
        self.entry_end = Entry(scoreboard_frame, width=entry_width)
        Label(scoreboard_frame, text="Session Start:", bg='white', anchor=W).grid(row=0, sticky=W)
        Label(scoreboard_frame, text="Session end:", bg='white', anchor=W).grid(row=2, sticky=W)
        self.entry_start.grid(row=1, sticky=W)
        self.entry_end.grid(row=3, sticky=W)

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
            self.entry_trial_dur,
            self.entry_track_period,
            self.check_conveyor_away,
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

        # Update list of available ports
        self.update_ports()

        # Default values
        self.entry_trial_dur.insert(0, 60000)
        self.conveyor_away_var.set(True)
        self.entry_track_period.insert(0, 50)
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
        self.counter = {}
        self.q = Queue()
        self.gui_update_ct = 0  # count number of times GUI has been updated

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

    def get_save_file(self):
        save_file = tkFileDialog.asksaveasfilename(
            defaultextension=".h5",
            filetypes=[
                ("HDF5 file", "*.h5 *.hdf5"),
                ("All files", "*.*")
            ]
        )
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

        # Define parameters
        # NOTE: Order is important here since this order is preserved when sending via serial.
        self.parameters['trial_duration'] = int(self.entry_trial_dur.get())
        self.parameters['conveyor_away'] = int(self.conveyor_away_var.get())
        self.parameters['track_period'] = int(self.entry_track_period.get())

        # Clear old data
        self.vel_trace.set_data([[], []])
        self.ax.set_xlim(0, self.parameters['trial_duration'])
        self.plot_canvas.draw()
        for obj in self.scoreboard_objs:
            obj.delete(0, END)
        
        # Initialize/clear old data
        self.trial_onset = np.zeros(1000, dtype='uint32')
        self.steps = np.zeros((2, 360000), dtype='uint32')
        self.track = np.zeros((2, 360000), dtype='int32')
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

        start_time = datetime.now()
        approx_end = start_time + timedelta(milliseconds=self.parameters['trial_duration'])
        self.start_time = start_time.strftime("%H:%M:%S")
        print("Session start ~ {}".format(self.start_time))
        self.entry_start.insert(0, self.start_time)
        self.entry_end.insert(0, '~' + approx_end.strftime("%H:%M:%S"))

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

        # Codes
        code_end = 0
        code_trial_start = 3
        code_track = 7

        # End on "Stop" button (by user)
        if self.stop.get():
            self.stop.set(False)
            self.ser.write("0")
            print("Stopped by user.")

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

            elif code == code_trial_start:
                self.trial_onset[self.counter['trial']] = ts
                self.counter['trial'] += 1

            elif code == code_track:
                dist = int(q_in[2])

                # Record tracking
                self.track[:, self.counter['track']] = [ts, dist]

                # Update plot
                X, Y = self.vel_trace.get_data()
                self.vel_trace.set_data([
                    np.append(X, ts),
                    np.append(Y, dist)
                ])
                
                # Increment counter
                self.counter['track'] += 1

        # Increment GUI update counter
        self.gui_update_ct += 1
        
        # Update plot every 0.5 s
        if self.gui_update_ct % 5 == 0:
            self.plot_canvas.draw()

        self.parent.after(refresh_rate, self.update_session, data_file)

    def stop_session(self, data_file):
        self.gui_util('stop')
        self.close_serial()
        end_time = datetime.now().strftime("%H:%M:%S")

        if data_file:
            behav_grp = data_file.create_group('behavior')
            behav_grp.create_dataset(name='trials', data=self.trial_onset[:self.counter['trial']], dtype='uint32')
            behav_grp.create_dataset(name='track', data=self.track[:, :self.counter['track']], dtype='int32')
            
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
    sys.stdout.write("Uploading parameters to Arduino: {}".format(values))
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
    root.wm_title("Odor presentation")
    if os.name == 'nt':
        root.iconbitmap(os.path.join(os.getcwd(), 'neuron.ico'))
    InputManager(root)
    root.mainloop()


if __name__ == '__main__':
    main()
