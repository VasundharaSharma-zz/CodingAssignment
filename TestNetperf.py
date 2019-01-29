# /usr/local/bin/python3.7
#
# Import the required modules
import subprocess
import shlex
import argparse
import ipaddress # Note: Works on Python 3 and would require explicit package installation on Python 2.7
import os
import shutil
from pathlib import Path

############################################################################################
#         Snapshot of Script Usage with the list of supported arguments                    #
#                                                                                          #
############################################################################################

'''
usage: TestNetperf.py [-h] [-m [SENDSIZELOCAL]] [-M [SENDSIZEREMOTE]]
    [-s [SOCKSIZELOCAL]] [-S [SOCKSIZEREMOTE]]
    hostIp port testLen loopCount

required arguments:
  hostIp                IP address of Host name to execute the Netperf Utility
  port                  Port number assocaited with Netperf
  testLen               Test run length (in Seconds)
  loopCount             number of iterations of the current Netperf test run

optional arguments:
  -h, --help             show this help message and exit
  -m [SENDSIZELOCAL],  --sendSizeLocal [SENDSIZELOCAL]
                         Local send size in bytes
  -M [SENDSIZEREMOTE], --sendSizeRemote [SENDSIZEREMOTE]
                         Remote send size in bytes
  -s [SOCKSIZELOCAL],  --sockSizeLocal [SOCKSIZELOCAL]
                         Local Send/Recv Socket Buffer size specified by value
  -S [SOCKSIZEREMOTE], --sockSizeRemote [SOCKSIZEREMOTE]
                         Remote Send/Recv Socket Buffer size specified by value
'''
############################################################################################
#         Class Perfmon definition and functions to implement throughput processing        #
#                                                                                          #
############################################################################################


class PerfMon:
    def __init__(self, cmd, iter):
        self.cmd = cmd
        self.iter = iter

    ## Function to run the given command and return the CLI output into a String, it is important to wait for the command to complete execution for netperf utility
    def run_command(self, command, wait=False):
        outString = ''
        try:
            if (wait):
                process = subprocess.Popen(command,
                                           stdout = subprocess.PIPE,
                                           shell=True)
                process.wait()
            else:
                process = subprocess.Popen(command,
                                           stdin = None,
                                           stdout = None,
                                           stderr = None,
                                           close_fds = True)
        
            (result, error) = process.communicate()
            output = result.decode() # convert byte object to string for further processing
            if output:
                # Capture output and concatenate it to String->outString
                if outString:
                    outString += ('\n'+output.strip()) # preserve the output format across multiple lines
                else:
                    outString += output.strip()
        except subprocess.CalledProcessError as e:
            sys.stderr.write(
                         "common::run_command() : [ERROR]: output = %s, error code = %s\n"
                         % (e.output, e.returncode))
        print(outString) # Prints the complete output from the command execution
        return outString


    ## Function to Parse ThroughPut Value from the Netperf command output
    def get_netperf_thruput(self, cliOut):
        try:
            if cliOut:
                lines = cliOut.split('\n')
                # Index the last line of the Netperf Output to parse the Throughput Value
                thruline = lines.pop()
                values = thruline.split(" ") # Capture all numeric data from the output
                thruput = values.pop() # Last numneric data represents the throughput value
                thruput = float(thruput)
        except ValueError:
                print('Throughput value not computed')
                raise ValueError('Throughput value not computed')
        else:
            return thruput


    ## Function to calculate average Throughput out of given 'N' iterations of Netperf command execution
    def get_average_thruput(self, cmd, numRun):
        avgThru = 0.0
        sum = 0.0
        for x in range(numRun):
            out = ''
            out = self.run_command(cmd, wait=True)
            thru = self.get_netperf_thruput(out)
            if thru:
                sum += thru
        avgThru = round((sum/numRun),2) ## Restricting average throughput value to 2 decimal places
        try:
            if avgThru > 0:
                print("Average Throughput: ",avgThru)
        except ValueError:
            if avgThru <= 0:
                print('Error in calculating average throughput')
                raise ValueError('Error in calculating average throughput')
        else:
            return avgThru

                
    ## Function to validate base directory and create empty file (touch)
    def touch(self,path):
        basedir = os.path.dirname(path)
        if not os.path.exists(basedir):
            os.makedirs(basedir)
            Path(path).touch()
            print("TEST")
            os.utime(path, None)


    ## Function to compare throughput value obtained in test run with previous results
    '''
        Actual throughput validation from Netperf output has dependencies on the enviornment (for example, TCP window tuning->Recv Sock Size), platform (for example,Interface bandwidth, link aggregation maximum supported bandwidth between the nodes etc., different OS ), network load, etc. Therefore, it would require additional information to derive the optimal BENCHMARK value to decide if the throughout test has a PASS/FAIL.
        For verification purposes, we can assume that the above required information is available for analysis and can be stored in a database and each successive test run can compare against the older results which have same or very similar dependencies.
        
        For this test run, we would simply store the throughput value in a file and do some basic
        calculation to determine PASS/FAIL result (Use the collected history of executions and fail patterns to achieve hands-free analysis of our latest results).
        
    '''
    def test_throughput(self, hostIP, port, testDuration, averageThroughput):
        RESULT_STRING = hostIP + ":" + port + ":" + testDuration

        # Initialize the variables to False
        PAST_RESULTS_FOUND = False
        TEST_PASSED = False

        if not os.path.exists('netperf_results.txt'):
            print("File: 'netperf_results.txt' does not exist, creating one.")
            open("netperf_results.txt", 'a').close()

        # check for any existing result entries in the Results file and process accordingly - create a file if it doesn't exists
        with open('netperf_results.txt') as inputFile:
            with open('temp_result.txt', 'w+') as tempFile:
                for line in inputFile:
                    if RESULT_STRING in line and not TEST_PASSED and not PAST_RESULTS_FOUND:
                        print('Found an entry which got past results from the test run.')
                        print(line)
                        PAST_RESULTS_FOUND = True
                        # fetch the throughput values for upto last 3 runs
                        # split the line from right most to have those 3 values in a list
                        line = line.rstrip()
                        throughputValues = line.split(";") # this will give us all the run values.
                        throughputValues = list(reversed(throughputValues)); # to place the Host details in the end
                        del throughputValues[-1] # to leave out the Host details stored in the netperf_results.txt
                        totalThroughputValues = len(throughputValues)
                        if totalThroughputValues > 0:
                            # got some values
                            for val in throughputValues:
                                if avg >= float(val):
                                    # pass the test case
                                    TEST_PASSED = True
                        if totalThroughputValues < 3:
                            # Go to the end of the LINE and add new throughput value for future use
                            line = line.rstrip() + ";" + str(avg)
                            tempFile.write(line)
                        else:
                             tempFile.write(line) # add the new entry

                if TEST_PASSED:
                    # TEST PASSED HERE
                    # Print the log and move on...
                    print("Netperf throughput test PASSED with an average value:", avg)

                if not PAST_RESULTS_FOUND:
                    # Go to the end of the file and add the entry in the file...for future usage.
                    # as we do not have benchmark values, we will just assume that test passed, as there
                    # are no past results to compare
                    newLine = RESULT_STRING + ";" + str(avg)
                    tempFile.write(newLine)
                    TEST_PASSED = True
                    print("Netperf throughput test PASSED with an average value:", avg)
                            
                if not TEST_PASSED:
                    # TEST FAILED HERE
                    # Print the log and move on...
                    print("Netperf throughput test FAILED with an average value:", avg)

        shutil.move('temp_result.txt', 'netperf_results.txt')


#### End of Class

######################################################################################################
#   Command Line Arguments Specifications and Parsing of the arguments                               #
#   Current version of script supports limited 'required' and 'optional' arguments from the          #
#   Netperf official support (can be extended)                                                       #
#   Run TestNetperf.py -h for options                                                                #
#   Sample Command: netperf -H 192.168.0.19 -l 5 -p 16604                                            #
#                   netperf -H 192.168.0.19 -l 5 -p 16604 -- -m 90000 -M 90000 -S 90000 -s 90000     #
#                   netperf -H 192.168.0.19 -l 5 -p 16604 -- -m 90000 -M 90000                       #
#   Sample loopCount: 20                                                                             #
######################################################################################################

# construct the argument parser and parse the command line arguments for the netperf command
ap = argparse.ArgumentParser()
ap.add_argument("hostIp",
                help="IP address or Host name to execute the Netperf Utility")
ap.add_argument("port", type=int,
                help="Port number associated with netserver")
ap.add_argument("testLen", type=int,
                help="Test run length (in Seconds)", default=120)
ap.add_argument("loopCount", type=int,
                help="number of iterations for looping Netperf test run", default=10)
ap.add_argument("-m", "--sendSizeLocal", nargs='?', type=int,
                help="Local send size in bytes", default=90000)
ap.add_argument("-M", "--sendSizeRemote", nargs='?', type=int,
                help="Remote send size in bytes", default=90000)
ap.add_argument("-s", "--sockSizeLocal", nargs='?', type=int,
                help="Local Send/Recv Socket Buffer size specified by value", default=90000)
ap.add_argument("-S", "--sockSizeRemote", nargs='?', type=int,
                help="Remote Send/Recv Socket Buffer size specified by value", default=90000)

args = vars(ap.parse_args()) # parses all command line arguments and stores in a list

# Process all the "required" command arguments to generate netperf command
loopNum = args["loopCount"]
command = "netperf"

# check if "host" argument is a valid Ipv4 address or a string representing hostname
if ((ipaddress.ip_address(args["hostIp"])) or (type(args["hostIp"] == str))):
    command+=" -H "+str(args["hostIp"]) # append the argument to the command string
else:
    print("Invalid input for:"+args["hostIp"]+"..Exiting !!")
    raise SystemExit

# check if given port number is a valid registered port in range 1024-49151
if 1024 <= args["port"] <= 49151:
    command+=" -p "+str(args["port"])
else:
    print("Invalid input for port="+str(args["port"])+"..Exiting !!")
    raise SystemExit

# check if given test length (in seconds) has a positive value
if args["testLen"] > 0:
    command+=" -l "+str(args["testLen"])
else:
    print("Invalid input for testLen="+str(args["testLen"])+"..Exiting !!")
    raise SystemExit

## Process Optional command arguments if provided by user
if 'sendSizeLocal' or 'sendSizeRemote' or 'sockSizeLocal' or 'sockSizeRemote' in args:
    command+=" -- " # append optional argument delimiter in the netperf command

## Process Optional Arguments one by one
# If the "given" optional arguments exist and have a positive value then append it to the command
if 'sendSizeLocal' in args and args["sendSizeLocal"] > 0:
    command+=" -m "+str(args["sendSizeLocal"])
if 'sendSizeRemote' in args and args["sendSizeRemote"] > 0:
    command+=" -M "+str(args["sendSizeRemote"])
if 'sockSizeLocal' in args and args["sockSizeLocal"] > 0:
    command+=" -s "+str(args["sockSizeLocal"])
if 'sockSizeRemote' in args and args["sockSizeRemote"] > 0:
    command+=" -S "+str(args["sockSizeRemote"])

print("Command: "+command+"\n") # final derived command string

#### End of Command Line Argument Parsing

############################################################################################
#         Driver Code to Execute netperf and process throughput                            #
#                                                                                          #
############################################################################################

# Create first Object of Class Perfmon and initialize it with Command and loopCount
p1 = PerfMon(command, loopNum)

# Run Netperf in loop for {LoopNum} and calculate Average throughtput value
avg = p1.get_average_thruput(p1.cmd,p1.iter)

# Throughput Verification for determining Test:PASS/FAIL (Experimental)
p1.test_throughput(str(args["hostIp"]), str(args["port"]), str(args["testLen"]), avg)

############################################################################################
#                                   End of Script                                          #
#                                                                                          #
############################################################################################
