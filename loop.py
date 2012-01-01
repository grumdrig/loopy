#!/usr/bin/python

"""Usage: loop.py OPTS COMMAND [-- WATCH...]

Wait for changes to FILEs NAMEd on the command line, Run the COMMAND
whenever one of them changes. (However, filenames following a '>' in
the command are not watched. AND preceding a filename with @ keeps it
from being watched.)

OPTS:
  -#        Run command through head -# (for some integer #)
  -i FNAME  Ignore changes to FNAME even if appears in COMMAND or WATCH
  -d        'Daemon' mode - run task in background and restart as needed
  -q        Print less info
  -a        Always restart when command quits
 
WATCH: Files listed after -- but are watched for changes

EXAMPLES:
  loop.py gcc test.c
    Recompile test.c whenever it changes

  loop.py make test -- *.c *.h
    Run make whenever a .c or .h file changes

  loop.py sed s/day/night/ \< dayfile \> nightfile
    Run sed whenever dayfile changes to produce nightfile. Note that
    the io redirection operators must be escaped. Also note that
    though nightfile is mentioned in the command, it's after a '>' and
    therefore not watched.
"""

import os, sys, time, itertools, signal

def main():
  HEAD = ''
  IGNORE = set()
  BACKGROUND = False
  QUIET = False
  ALWAYS = False

  args = sys.argv[1:]
  while (args or [''])[0].startswith('-'):
    opt = args.pop(0)
    if not args:
      usage()
    if opt == '-i':
      IGNORE.add(args.pop(0))
    elif opt == '-d':
      BACKGROUND = True
    elif opt == '-q':
      QUIET = True
    elif opt == '-a':
      ALWAYS = True
    else:
      HEAD = ' 2>&1 | head ' + opt

  for i in range(len(args)):
    if args[i][:1] == '@':
      args[i] = args[i][1:]
      IGNORE.add(args[i])

  if not args:
    usage()

  # Split args into [COMMAND, WATCH]
  cfi = [list(g) for k,g in itertools.groupby(args, lambda x: x != '--') if k]

  command = cfi.pop(0)
  filenames = [a for a,b in zip(command, [0] + command[:-1]) if b != '>']
  filenames = set([f for f in filenames if os.path.exists(f)])
  filenames |= set(cfi and cfi.pop(0))
  filenames -= IGNORE

  if not BACKGROUND:
    command = ' '.join(command)

  pid = None
  mtime = None
  while True:
    m = [os.stat(filename).st_mtime for filename in filenames
         if os.path.exists(filename)]

    if not BACKGROUND:

      if (mtime != m) or ALWAYS:
        #os.system('clear')
        print '$ ' + command
        os.system(command + HEAD)
        mtime = m
        if not (QUIET or ALWAYS):
          print "Watching:", ', '.join(filenames)

      time.sleep(1)

    else:

      if mtime != m:
        pid = restart(pid, command)
        mtime = m
      else:
        try:
          os.kill(pid, 0)
        except:
          pid = restart(pid, command)

      try:
        time.sleep(1)
      except KeyboardInterrupt:
        print "\nKilling", pid, "^C again to quit"
        if pid:
          os.kill(pid, signal.SIGTERM)
          pid = None
        try:
          time.sleep(1)
        except KeyboardInterrupt:
          print
          break



def usage():
    print __doc__
    sys.exit()


def restart(pid, command):
  if pid:
    print "Killing pid", pid
    os.kill(pid, signal.SIGTERM)
  pid = os.spawnlp(os.P_NOWAIT, command[0], *command)
  print "Started", pid
  return pid


if __name__ == '__main__':
  main()
