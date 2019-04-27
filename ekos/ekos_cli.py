#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import sys
import time

# https://dbus.freedesktop.org/doc/dbus-python/index.html
import dbus


class Ekos():
    def __init__(self):
        # user login session
        self.session_bus = dbus.SessionBus()
        self.start_ekos_proxy = None
        self.start_ekos_iface = None
        self.ekos_proxy = None
        self.ekos_iface = None
        self.scheduler_proxy = None
        self.scheduler_iface = None

    def setup_start_ekos_iface(self):
        try:
            # proxy object
            self.start_ekos_proxy = self.session_bus.get_object("org.kde.kstars",  # bus name
                                                                "/kstars/MainWindow_1/actions/ekos"  # object path
                                                                )
            # interface object
            self.start_ekos_iface = dbus.Interface(self.start_ekos_proxy, 'org.qtproject.Qt.QAction')
        except dbus.DBusException as dbe:
            print(dbe)
            sys.exit(1)

    def setup_ekos_iface(self):
        # if self.start_ekos_iface is None:
        #     self.setup_start_ekos_iface()
        try:
            self.ekos_proxy = self.session_bus.get_object("org.kde.kstars",
                                                          "/KStars/Ekos"
                                                          )
            # ekos interface
            self.ekos_iface = dbus.Interface(self.ekos_proxy, 'org.kde.kstars.Ekos')
        except dbus.DBusException as dbe:
            print(dbe)
            sys.exit(1)

    def setup_scheduler_iface(self):
        try:
            # https://api.kde.org/extragear-api/edu-apidocs/kstars/html/classEkos_1_1Scheduler.html
            self.scheduler_proxy = self.session_bus.get_object("org.kde.kstars",
                                                               "/KStars/Ekos/Scheduler"
                                                               )
            self.scheduler_iface = dbus.Interface(self.scheduler_proxy, "org.kde.kstars.Ekos.Scheduler")
        except dbus.DBusException as dbe:
            print(dbe)
            sys.exit(1)

    def start_ekos(self):
        print("Start Ekos")
        if self.start_ekos_iface is None:
            self.setup_start_ekos_iface()
        self.start_ekos_iface.trigger()

    def stop_ekos(self):
        print("Stop Ekos")
        if self.ekos_iface is None:
            self.setup_ekos_iface()
        self.ekos_iface.stop()

    def load_and_start_profile(self, profile):
        print("Load {} profile".format(profile))
        if self.ekos_iface is None:
            self.setup_ekos_iface()
        self.ekos_iface.setProfile(profile)
        print("Start {} profile".format(profile))
        self.ekos_iface.start()
        self.ekos_iface.connectDevices()
        print("TODO Waiting for INDI devices...")
        time.sleep(5)

    def load_schedule(self, schedule):
        print("Load {} schedule".format(schedule))
        if self.scheduler_iface is None:
            self.setup_scheduler_iface()
        self.scheduler_iface.loadScheduler(schedule)

    def start_scheduler(self):
        print("Start scheduler")
        if self.scheduler_iface is None:
            self.setup_scheduler_iface()
        self.scheduler_iface.start()

    def stop_scheduler(self):
        print("Stop scheduler")
        if self.scheduler_iface is None:
            self.setup_scheduler_iface()
        self.scheduler_iface.stop()

    def reset_scheduler(self):
        print("Reset all jobs in the scheduler")
        if self.scheduler_iface is None:
            self.setup_scheduler_iface()
        self.scheduler_iface.resetAllJobs()


def main():
    parser = argparse.ArgumentParser(description='Ekos cli')
    parser.add_argument('--start_ekos', action='store_true', help='start ekos')
    parser.add_argument('--stop_ekos', action='store_true', help='stop ekos')
    parser.add_argument('--profile', required=False, type=str, help='equipment profile name, fi Simulators')
    parser.add_argument('--load_schedule', required=False, type=str,
                        help='schedule .esl file path. Note: this replaces the entire observation list with this single entry.')
    parser.add_argument('--start_scheduler', action='store_true', help='start the scheduler')
    parser.add_argument('--stop_scheduler', action='store_true', help='stop the scheduler')
    parser.add_argument('--reset_scheduler', action='store_true', help='reset all jobs in the scheduler')
    args = parser.parse_args()

    ekos = Ekos()
    if args.start_ekos:
        ekos.start_ekos()
    if args.stop_ekos:
        ekos.stop_ekos()
    if args.profile:
        ekos.load_and_start_profile(args.profile)
    if args.load_schedule:
        ekos.load_schedule(args.load_schedule)
    if args.start_scheduler:
        ekos.start_scheduler()
    if args.stop_scheduler:
        ekos.stop_scheduler()
    if args.reset_scheduler:
        ekos.reset_scheduler()


if __name__ == "__main__":
    main()
