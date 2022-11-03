Usage: loop.py OPTS COMMAND [-- WATCH...]
       loop.py OPTS COMMAND [-- WATCH...] ++ OPTS COMMAND [-- WATCH...] ...
       loop.py --for NAME in FILE do OPTS COMMAND [-- WATCH...] ...
       loop.py [-L ARGS]
       loop.py -F LOOPFILE ARGS

Wait for changes to FILEs NAMEd on the command line, Run the COMMAND
whenever one of them changes. (However, filenames following a '>' in
the command are not watched. AND preceding a filename with @ keeps it
from being watched.)

Initial OPTS:
	-q        Print less info
	-v        Print more info
	-f        Faster polling for changes
	-F FNAME  Load the loopfile FNAME
	-L        Same as `-F Loopfile`
These options must come first, and apply to all command loops.

Per-command OPTS:
	-#        Run command through head -# (for some integer #)
	-w FNAME  Watch FNAME for changes
	-i FNAME  Ignore changes to FNAME even if appears in COMMAND or WATCH
	-I        Ignore all command line names not explicitly in WATCH
	-d        'Daemon' mode - start task in background and restart as needed
	-a        Always restart when command quits
	-x        Run command once on startup without waiting for changes
	--for...  Apply command to multiple parameters, explained below

WATCH: Files listed after -- or specified with -w are watched for changes
			 without being part of the command

Multiple command watch loops can be specified by separating them with ++.

Specifying a loopfile with -F causes the options and commands to be read
from lines in the loopfile. Each nonblank line is parsed as if they were
on the command line. Lines beginning with "#" are treated as comments.

Arguments after -F FNAME or -L are passed to the loopfile as $1, $2, etc.
These and other environment variables are substituted in the loopfile.

Running loop.py without any arguments causes it to look for the loopfile
named "Loopfile" in the current directory. The Loopfile contains command line
arguments that would otherwise be passed to loop.py.

Command loops can be duplicated for multiple files with `--for`. The
pattern is `--for VAR in ARG1 ARG2 ... do ...`. In the command, $VAR will
be replaced with each ARG in turn.

Hitting the enter key causes all commands to run (and/or daemons to be
restarted). Or hitting <task number> <enter> will trigger just that command.

EXAMPLES:
	loop.py gcc test.c
		Recompile test.c whenever it changes

	loop.py a.out
		Run a.out whenever it changes

	loop.py gcc test.c ++ a.out
		Do both

	loop.py make test -- *.c *.h
		Run make whenever a .c or .h file changes

	loop.py sed s/day/night/ \< dayfile \> nightfile
		Run sed whenever dayfile changes to produce nightfile. Note that
		the io redirection operators must be escaped. Also note that
		though nightfile is mentioned in the command, it's after a '>'
		and therefore not watched.

	loop.py swiftc -emit-library helper.swift ++ swiftc -lhelper program.swift -- libhelper.dylib ++ ./program
		Recompile the library "helper" when "helper.swift" changes. And:
		Recompile "program" when program.swift or the library changes. And:
		Run the program whenever it is regenerated.

	loop.py --for FILE in *.c do cc -o $FILE
		Compile any C file that changes

