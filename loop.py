#!/usr/bin/python

"""Usage: loop.py OPTS COMMAND [-- WATCH...]
       loop.py OPTS COMMAND [--WATCH...] ++ OPTS COMMAND [--WATCH...] ...
       loop.py [-F LOOPFILE]

Wait for changes to FILEs NAMEd on the command line, Run the COMMAND
whenever one of them changes. (However, filenames following a '>' in
the command are not watched. AND preceding a filename with @ keeps it
from being watched.)

OPTS:
  -#        Run command through head -# (for some integer #)
  -w FNAME  Watch FNAME for changes
  -i FNAME  Ignore changes to FNAME even if appears in COMMAND or WATCH
  -I        Ignore all command line names not explicitly in WATCH
  -d        'Daemon' mode - start task in background and restart as needed
  -q        Print less info
  -V        Print more info
  -a        Always restart when command quits
  -f        Faster polling for changes (applies to all command watch loops)
  -x        Run command once on startup without waiting for changes
  -F FNAME  Load the loopfile FNAME

WATCH: Files listed after -- or specified with -w are watched for changes
       without being part of the command

Multiple command watch loops can be specified by separating them with ++.

Specifying a loopfile with -F causes the options and commands to be read
from lines in the loopfile. Each nonblank line is parsed as if they were
on the command line. Lines beginning with "#" are treated as comments.

Running loop.py without any arguments causes it to look for the loopfile
named "Loopfile" in the current directory.

Hitting the enter key causes all commands to run (and/or daemons to be restarted).

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

  loop.py swiftc -emit-library helper.swift ++ swiftc -lhelper program.swift -- libhelper.dylib ++ ./program
    Recompile the library "helper" when "helper.swift" changes. And:
    Recompile "program" when program.swift or the library changes. And:
    Run the program whenever it is regenerated.
"""

import os, sys, time, itertools, signal


SLEEPTIME = 1


def main():
  args = sys.argv[1:]
  LOOPFILE = None
  if not args:
    LOOPFILE = "Loopfile"
  if (len(args) == 2) and (args[0] == '-F'):
    LOOPFILE = args[1]
    args = args[2:]
  if LOOPFILE:
    if not os.path.exists(LOOPFILE):
      usage()

    tasks = [os.path.expandvars(line).split() for line in open(LOOPFILE, "rt").readlines() if line.strip() and line[0] != "#"]
  else:
    tasks = [list(g) for k,g in itertools.groupby(args, lambda x: x != '++') if k]

  tasks = map(lambda task: Task(task), tasks)
  while True:
    for task in tasks:
      task.checkForChanges()

    if enterKeyHasBeenHit():
      for task in tasks:
        task.mtime = None
    else:
      try:
        time.sleep(SLEEPTIME)
      except KeyboardInterrupt:
        killed = 0
        for task in tasks:
          if task.pid:
            print "\nKilling", task.pid
            os.kill(task.pid, signal.SIGTERM)
            task.pid = None
            killed += 1
        if killed:
          print "^C again to quit"
          try:
            time.sleep(1)
          except KeyboardInterrupt:
            print
            sys.exit(0)
        else:
          sys.exit(0)


class Task:
  def __init__(self, args):
    IGNORE = set()
    WATCH = set()
    AUTOWATCH = True
    WAIT = True
    self.HEAD = ''
    self.BACKGROUND = False
    self.VERBOSITY = 0
    self.ALWAYS = False
    global SLEEPTIME

    while args and args[0].startswith('-'):
      opt = args.pop(0)
      if not args:
        usage()
      if opt == '-w':
        WATCH.add(args.pop(0))
      elif opt == '-i':
        IGNORE.add(args.pop(0))
      elif opt == '-I':
        AUTOWATCH = False
      elif opt == '-d':
        self.BACKGROUND = True
      elif opt == '-q':
        self.VERBOSITY -= 1
      elif opt == '-v':
        self.VERBOSITY += 1
      elif opt == '-a':
        self.ALWAYS = True
      elif opt == '-f':
        SLEEPTIME /= 4
      elif opt == '-x':
        WAIT = False
      else:
        self.HEAD = ' 2>&1 | head ' + opt

    for i in range(len(args)):
      if args[i][:1] == '@':
        args[i] = args[i][1:]
        IGNORE.add(args[i])

    if not args:
      usage()

    # Split args into [COMMAND, WATCH]
    cfi = [list(g) for k,g in itertools.groupby(args, lambda x: x != '--') if k]

    self.command = cfi.pop(0)
    filenames = [a for a,b in zip(self.command, [0] + self.command[:-1]) if b != '>']
    filenames = set([f for f in filenames if os.path.exists(f) and AUTOWATCH])
    filenames |= set(cfi and cfi.pop(0))
    filenames |= WATCH
    filenames -= IGNORE
    self.filenames = filenames

    if not self.BACKGROUND:
      self.command = ' '.join(self.command)

    self.pid = None
    self.mtime = None
    if WAIT and not self.BACKGROUND:
      self.mtime = [os.stat(filename).st_mtime for filename in self.filenames
                    if os.path.exists(filename)]
    if self.VERBOSITY > 0:
      print self.command, self.filenames


  def checkForChanges(self):
    m = [os.stat(filename).st_mtime for filename in self.filenames
         if os.path.exists(filename)]
    if self.ALWAYS:
      m = None

    if not self.BACKGROUND:

      if self.mtime != m:
        print '$ ' + self.command
        os.system(self.command + self.HEAD)
        self.mtime = m
        if not (self.VERBOSITY >= 0 or self.ALWAYS):
          print "############################################################"
          print "Watching:", ', '.join(self.filenames)

    else:

      if self.mtime != m:
        self.pid = restart(self.pid, self.command)
        self.mtime = m
      else:
        try:
          os.kill(self.pid, 0)  # look for the running process
        except:
          self.pid = restart(self.pid, self.command)


def usage():
    print __doc__
    sys.exit()


def enterKeyHasBeenHit():
  import select
  i,o,e = select.select([sys.stdin],[],[],0.0001)
  for s in i:
    if s == sys.stdin:
      return sys.stdin.readline()
  return False


def restart(pid, command):
  if pid:
    print "Killing pid", pid
    os.kill(pid, signal.SIGTERM)
  pid = os.spawnlp(os.P_NOWAIT, command[0], *command)
  print "Started pid", pid
  return pid


if __name__ == '__main__':
  main()
