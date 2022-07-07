import curses, curses.wrapper
import time
import glob
from pmc_turbo.utils import decode_science_stack_housekeeping
from pmc_turbo.communication import packet_classes


def display_status(stdscr, housekeeping_dir):
    # Set non-blocking input
    stdscr.nodelay(1)
    run = 1

    curses.init_pair(1, curses.COLOR_BLUE, curses.COLOR_BLACK)
    curses.init_pair(2, curses.COLOR_GREEN, curses.COLOR_BLACK)
    curses.init_pair(3, curses.COLOR_WHITE, curses.COLOR_RED)
    keycol = curses.color_pair(1)
    valcol = curses.color_pair(2)
    errcol = curses.color_pair(3)
    status = {}

    # Loop
    while (run):

        # Get newest gse_housekeeping_packet status
        gse_housekeeping_packets = glob.glob(housekeeping_dir)
        gse_housekeeping_packets.sort()
        with open(gse_housekeeping_packets[-1], 'rb') as f:
            buffer = f.read()
        gse_housekeeping_packet = packet_classes.GSEPacket(buffer=buffer)

        bins = decode_science_stack_housekeeping.interpret_digital_bytes_housekeeping_payload(
            gse_housekeeping_packet.payload[:2])

        floats = decode_science_stack_housekeeping.interpret_payload(
            gse_housekeeping_packet.payload)
        status = decode_science_stack_housekeeping.pack_floats_into_dict(floats)
        status['digital'] = bins

        # Reset screen
        stdscr.erase()

        # Draw border
        stdscr.border()

        # Get dimensions
        (ymax, xmax) = stdscr.getmaxyx()

        # Display main status info
        onecol = False  # Set True for one-column format
        col = 2
        curline = 0
        # if new_data:
        stdscr.addstr(curline, col, "Current status:", keycol)
        # else:
        #     stdscr.addstr(curline, col, "Last status (no connection):", errcol)

        curline += 2
        flip = 0
        for k, v in list(status.items()):
            if (curline < ymax - 3):
                stdscr.addstr(curline, col, "%27.27s : " % k, keycol)
                value = str(v)[:32]
                stdscr.addstr("%27.27s" % value, valcol)
            else:
                stdscr.addstr(ymax - 3, col, "-- Increase window size --", errcol)
            if (flip or onecol):
                curline += 1
                col = 2
                flip = 0
            else:
                col = 60
                flip = 1
        # Bottom info line
        stdscr.addstr(ymax - 2, col, "Last update: " + time.asctime() \
                      + "  -  Press 'q' to quit")

        # Redraw screen
        stdscr.refresh()

        # Sleep a bit
        time.sleep(.27)

        # Look for input
        c = stdscr.getch()
        while (c != curses.ERR):
            if (c == ord('q')):
                run = 0
            c = stdscr.getch()


if __name__ == "__main__":
    import sys

    housekeeping_dir = sys.argv[1]
    try:
        curses.wrapper(display_status, housekeeping_dir)
    except KeyboardInterrupt:
        print("Exiting...")
