#!/usr/bin/env python
#########################################################################################
#
# PTCLM.py
#
# Python script to create datasets to run point simulations of CLM4
# using Tower Datasets for Ameriflux tower sites, using the CESM1
# framework.
#
# Python script originally created by: 
#
#  Daniel M. Riccciuto, Dali Wang, Peter E. Thornton, Wilfred M. Poist
#  of Environmental Sciences Division, Oak Ridge National Lab.
#
#  Quinn Thomas
#  of Cornell University
#
#  Modified by Erik Kluzek (NCAR) to be incorporated as a standard part of CLM4.
#
#  For help on PTCLM.py type:
#
#   PTCLM.py --help
#
#  Also see the README file
#
#  Requirements:
#
#  python, UNIX shell, NCL (NCAR Command Language),
#  GNU make, Fortran compiler, C compiler
#
# NOTE:  mksurfdata_map, and gen_domain  must be compiled!
#           You should only have to compile them once.
#           you must also have ncl installed.
#
#########################################################################################
description = 'Python script to create datasets to run single point simulations with tower site data.'
import os, csv, time, re, sys, shlex, subprocess
from   xml.sax.handler import ContentHandler
from   xml.sax         import make_parser 

######  THE ERROR FUNCTION
##############################################################

def error( desc ):
     "error function"
     print "ERROR("+sys.argv[0]+"):: "+desc
     os.abort()

######  SET SOME VARIABLES ##############################################################

#configure case options          
#run time defaults
defmyrun_units="default"  #default time units to run
defmyrun_n=-999           #default number of time to run
defSitesGroup = "EXAMPLE" #default site group name

cesm_input    = " "
filen         = " "
histrcp       = str(-999.9)
mydatadir     = "mydatafiles"
clmphysvers   = "clm4_5"
clmnmlusecase = "2000_control"
datm_mode     = "CLM1PT"

######  GET VERSION INFORMATION #########################################################

if sys.version_info < (2, 4):
    error( "The version of Python being used is too old for PTCLM" )


svnurl="$HeadURL$"
if   ( svnurl.split('/')[4] == "trunk"       ):
   svnvers="scripts_trunk"
elif ( svnurl.split('/')[4] == "trunk_tags"  ):
   svnvers=svnurl.split('/')[5]
elif ( svnurl.split('/')[4] == "branches"    ):
   svnvers="scripts_branch_"+svnurl.split('/')[5]
elif ( svnurl.split('/')[4] == "branch_tags" ):
   svnvers="scripts_brnchtag_"+svnurl.split('/')[6]
else:
   print( "Error getting version from: "+svnurl)
   os.abort()
version="PTCLM"+str(2.0)+"_"+svnvers

### PARSE THE COMMAND LINE INPUT ########################################################

from optparse import OptionParser, OptionGroup

#parse arguments
cmdline = ""
for arg in sys.argv:
    cmdline = cmdline+arg+" "
parser = OptionParser( usage="%prog [options] -d inputdatadir -m machine -s sitename", description=description, version=version )
required = OptionGroup( parser, "Required Options" )
required.add_option("-d", "--cesmdata", dest="cesm_input", default=" ", \
                  help="Location of CCSM input data")
required.add_option("-m", "--machine", dest="mymachine", default="none" \
                  ,help="Machine, valid CESM script machine (-m list to list valid machines)")
required.add_option("-s", "--site", dest="mysite", default="none", \
                  help="Site-code to run, FLUXNET code (-s list to list valid names)")
parser.add_option_group(required)
options  = OptionGroup( parser, "Configure and Run Options" )
options.add_option("--cesm_root", dest="base_cesm", \
                  default=" ", help = \
                  "Root CESM directory (top level directory with models and scripts subdirs)")
options.add_option("--debug", dest="debug", action="store_true", default=False, \
                  help="Flag to turn on debug mode so won't run, but display what would happen")
options.add_option("--clmnmlusecase", dest="clmnmlusecase", default=clmnmlusecase, \
                  help="CLM namelist use case to use" )
options.add_option("--datm_mode", dest="datm_mode", default=datm_mode, \
                  help="DATM_MODE to use" )
options.add_option("--phys", dest="clmphysvers", default=clmphysvers, \
                  help="CLM physics version to use" )
options.add_option("--list", dest="list", default=False, action="store_true", \
                  help="List all valid: sites and machines")
options.add_option("--mydatadir", dest="mydatadir", default=mydatadir \
                  ,help="Directory of where to put your data files (files will be under subdirectories for each site)" )
options.add_option("--namelist", dest="namelist", default=" " \
                  ,help="List of namelist items to add to CLM namelist "+ \
                        "(example: --namelist=\"hist_fincl1='TG',hist_nhtfrq=-1\"" )
options.add_option("--use_tower_yrs",action="store_true",\
                  dest="use_tower_yrs",default=False,\
                  help="Use the global forcing data year that corresponds to the tower years (for cases using global forcing)")
options.add_option("--run_n", dest="myrun_n", default=defmyrun_n, \
                  help="Number of time units to run simulation" )
options.add_option("--run_units", dest="myrun_units", default=defmyrun_units, \
                  help="Time units to run simulation (steps,days,years, etc.)")
options.add_option("--quiet", action="store_true", \
                  dest="quiet", default=False, \
                  help="Print minimul information on what the script is doing")
options.add_option("--cycle_forcing", action="store_true", \
                  dest="cycle_forcing", default=False, \
                  help="Cycle over the forcing data rather than do one run through (modifies start/end year to get this to work)")
options.add_option("--sitegroupname", dest="sitegroup", default=defSitesGroup, \
                  help="Name of the group of sites to search for you selected site in "+ \
                  "(look for prefix group names in the PTCLM_sitedata directory)")
options.add_option("--verbose", action="store_true", \
                  dest="verbose", default=False, \
                  help="Print out extra information on what the script is doing")
parser.add_option_group(options)

indatgengroup = OptionGroup( parser, "Input data generation options", \
                  "These are options having to do with generation of input datasets.  " )
parser.add_option_group(indatgengroup)
indatgengroup.add_option("--pftgrid", dest="pftgrid", help = \
                  "Use pft information from global gridded file (rather than site data)", \
                  action="store_true", default=False)
indatgengroup.add_option("--soilgrid", dest="soilgrid", help = \
                  "Use soil information from global gridded file (rather than site data)",\
                   action="store_true", default=False)
indatgengroup.add_option("--mksurfdata_opts", dest="mksurfdata_opts", help = \
                  "Options to send directly to mksurfdata_map",\
                   default=" ")
versiongroup  = OptionGroup( parser, "Main Script Version Id: $Id$ Scripts URL: "+svnurl )
parser.add_option_group(versiongroup)

(options, args) = parser.parse_args()
if len(args) != 0:
    parser.error("incorrect number of arguments")

### END PARSE THE COMMAND LINE INPUT ####################################################

### SOME FUNCTIONS    ###################################################################

def system( cmd ):
     "system function with error checking and debug prining"
     if plev>0: print "Run command: "+cmd
     # Error check that command exists
     firstspace = cmd.index(" ");
     if ( firstspace == -1 ):
        justcmd = cmd
     else:
        justcmd = cmd[:firstspace]
     if ( cmd.index("/") != -1 ):
        if ( not os.path.exists(justcmd) ): 
           error( "Error command does NOT exist: "+justcmd );
     else:
        rcode = os.system( "which "+justcmd )
        if ( rcode != 0 ):
           error( "Error command is NOT in path: "+justcmd )
     # Now actually run the command if not debug or if create_newcase
     if ( not options.debug or cmd.startswith( "./create_newcase" ) ):
        rcode = os.system( cmd )
     else: rcode = 0
     if ( rcode != 0 ):
        error( "Error running command: "+cmd )
        if ( os.path.isfile(filen) ):
           output = open( filen,'a')
           output.write(cmd+"\n")
           output.close

def queryFilename( queryopts, filetype ):
    "query the XML database to get a filename"
    query = abs_base_cesm+"/models/lnd/clm/bld/queryDefaultNamelist.pl -silent " \
             +"-justvalue "
    if ( cesm_input != " " ): 
       query = query + " -csmdata "+cesm_input
    cmd = query+queryopts+" -var "+filetype
    file = os.popen( cmd )
    filename = file.read() 
    if ( file.close() != None ):
       print "Query = "+cmd
       error( "Error getting file from XML database" )
    # Remove the trailing new line from the filename
    if ( (filename == None) or (filename == "") ): 
       print "Query = "+cmd
       error( "Trouble finding file from XML database: "+filetype )
    return( filename.replace( "\n", "" ) )

def xmlchange_env_value( var, value ):
     'Function to set the value of a variable in one of the env_*.xml files'
     change = "./xmlchange"
     cmd = change+" "+var+"="+value
     filex = data_dir+"/xmlchange_cmnds"
     output = open( filex,'a')
     output.write(cmd+"\n")
     output.close
     system( "/bin/chmod +x "+filex )

def write_datm_namelistdefaults_file( dir ):
     "Write namelist_defaults_datm.xml file"
     datm_src_dir = data_dir+"/SourceMods/src.datm";
     system( "/bin/mkdir -p "+datm_src_dir )
     file = datm_src_dir+"/namelist_defaults_datm.xml"
     output = open( file,'w')
     filestrings = ( '<?xml version="1.0"?>', \
     ' ', \
     '<?xml-stylesheet type="text/xsl" href="namelist_defaults.xsl"?>', \
     ' ', \
     '<namelist_defaults>', \
     ' ', \
     '</namelist_defaults>' )
     # write out file
     for line in filestrings:
        output.write(line+"\n")
        # Add data directory for files
        if ( line.find( "<namelist_defaults>" ) != -1 ):
           output.write('\n')
           value = '<strm_datdir stream="CLM1PT.CLM_USRDAT">'+dir+'</strm_datdir>\n'
           output.write(value)

     output.close


if sys.version_info < (2, 5):
   def rpartition( string, sep ):
       'Reverse order of dividing string by seperator'
       before = string[0:string.rfind(sep)];
       after  = string[before.count(""):];
       return ( before, sep, after )
#
# Some classes
#

#
# List the machines in the config_machines.xml file
#
class MachineList( ContentHandler ):

   def startDocument(self):
     self.list = [];
   
   def startElement(self, name, attrs):
     if name == 'machine':     
       self.list.append( str( attrs.get('MACH',"") ) )

   def endDocument(self):
     print "\nValid Machines: "
     for machine in self.list:
        print str(machine)
     print "\n\n";

###### SET OPTIONS BASED ON INPUT FROM PARSER  ##########################################

mymachine  = options.mymachine
mysite     = options.mysite
SitesGroup = options.sitegroup
infohelp   = "\n\n Use --help option for help on usage.\n";
if(options.list):
    mymachine = "list"
    mysite    = "list"
if ( mysite == "none" ): parser.error("sitename is a required argument, set it to a valid value"+infohelp )
if ( options.verbose and options.quiet ):
    parser.error( "options quiet and verbose are mutually exclusive"+infohelp )

if (   options.verbose ): plev = 2
elif ( options.quiet   ): plev = 0
else:                     plev = 1

sitedata=SitesGroup+"_sitedata.txt"
soildata=SitesGroup+"_soildata.txt"
pftdata=SitesGroup+"_pftdata.txt"


if plev>0: print "---------------- PTCLM version "+str(version)+"-----------------------------\n"
if plev>0: print "   "+cmdline+"\n"
if plev>0: print "   OPTIONS:\n" 
if plev>0: print "Site name:\t\t\t\t\t\t"+mysite+"\n"

if plev>0: print "CESM machine:\t\t\t\t\t\t"+options.mymachine

base_cesm = options.base_cesm
if base_cesm == " ":
    #assume base directory is one level up from where script
    #  is executed, if not specified
    stdout    = os.popen("cd ../../../../../..; pwd")
    base_cesm = os.path.abspath( stdout.read().rstrip( ) )
    ptclm_dir = base_cesm+"/scripts/ccsm_utils/Tools/lnd/clm/PTCLM"
else:
    stdout    = os.popen("pwd")
    ptclm_dir = stdout.read().rstrip( )

abs_base_cesm = os.path.abspath( base_cesm )
if plev>0: print "Root CLM directory:\t\t\t\t\t"+abs_base_cesm

if plev>0:     print "Sites group name:\t\t\t\t\t"+SitesGroup

if plev>0: print "** Surface data file will be built using site-level data " + \
          "when available unless otherwise specified ** \n"
if plev>0: print "\tExtract PFT data from gridded files:\t\t"+str(options.pftgrid)
if plev>0: print "\tExtract soil data from gridded files:\t\t"+str(options.soilgrid)

if(mymachine == "list"):
    machXML = make_parser()
    machXML.setContentHandler(MachineList()) 
    cfgmach = abs_base_cesm+"/scripts/ccsm_utils/Machines/config_machines.xml";
    if ( not os.path.exists( cfgmach ) ): parser.error("File does NOT exist:"+cfgmach)
    machXML.parse( cfgmach )


###### END SET OPTIONS BASED ON INPUT FROM PARSER  ######################################

########## GET SITE LAT, LON, AND TOWER MET YEARS #######################################

siteDir = "PTCLM_sitedata"
os.chdir(ptclm_dir+"/"+siteDir)
#get lat/lon, start/end years from sitedata file
if plev>0: print "\nOpen Site data file: "+siteDir+"/"+sitedata+"\n"
AFdatareader = csv.reader(open(sitedata, "rb"))
if ( mysite == "list" ):  plev = 2
for row in AFdatareader:
    if plev>1: print " site = %9s name: %-55s Region: %12s Campaign: %s" % ( row[0], row[1], row[2], row[10] )
    if row[0] == mysite:
        lon=float(row[3])
        if (lon < 0):
            lon=360.0+float(row[3]) 
        lat=float(row[4])
        startyear=int(row[6])
        endyear=int(row[7])
        alignyear = int(row[8])
        timestep  = int(row[9])

# Exit early for list options
if ( mysite == "list" or mymachine == "list" ): 
  exit()

# inputdata directory -- set after list options
cesm_input=options.cesm_input
if cesm_input == " ":
   parser.error( "inputdatadir is a required argument, set it to the directory where you have your inputdata"+infohelp )
if plev>0: print "CESM input data directory:\t\t\t\t"+cesm_input
#define data and utility directories
mask          = "navy"
clmusrdatname = "1x1pt_"+mysite
clmusrdat     = " -usrname "+clmusrdatname
clmres        = clmusrdatname
clmmask       = "navy"
myres         = "CLM_USRDAT"  #single-point mode (don't change)

clm_tools   = abs_base_cesm+'/models/lnd/clm/tools'
gen_dom_dir = abs_base_cesm+'/tools/mapping/gen_domain_files'
mkmapgrd_dir= clm_tools+'/shared/mkmapgrids'
mkmapdat_dir= clm_tools+'/shared/mkmapdata'
clm_input   = cesm_input+'/lnd/clm2'
datm_input  = cesm_input+'/atm/datm7'

if ( options.mydatadir.startswith("/") ):
   data_dir    = options.mydatadir
else:
   data_dir    = ptclm_dir+'/mydatafiles'

data_dir    = data_dir+"/"+clmusrdatname
if ( not os.path.exists( data_dir ) ): system( "/bin/mkdir -p "+data_dir )

if plev>0: print "----------------------------------------------------------------\n"

############# WRITE OUT README FILE ON DATA ##############################################

os.chdir(ptclm_dir)      

opt = " "
if ( mymachine == "none" ): parser.error( "machine is a required argument, set it to a valid value"+infohelp )

clmnmlusecase    = options.clmnmlusecase

filen = data_dir+"/README.PTCLM"
if plev>0: print "Write "+filen+" with command line"
output = open( filen,'w')
output.write(cmdline+"\n")
output.close

############# GET SIM_YEAR, RCP and SIM_YEAR_RANGE based on USE-CASE ####################
############# CLM configure ensures naming conventions are followed  ####################
############# And setup Query options based on them #####################################

if (   clmnmlusecase.endswith("_transient") ):
     transient = re.search('^([0-9]+-[0-9]+)_*(.*)_(transient$)',   clmnmlusecase )
     if ( transient ):
        sim_year_range = transient.group(1)
        sim_year       = re.search( '^([0-9]+)-',    transient.group(1) ).group(1)
        rcpcase        = re.search( '^rcp([0-9.]+)', transient.group(2) )
        if ( rcpcase == None ): rcp = histrcp
        else:                   rcp = rcpcase.group(1)
     elif ( clmnmlusecase.startswith("20thC_") ):
        sim_year_range = "1850-2000"
        sim_year       = "1850"
        rcp            = histrcp
     else:
        error( "Can not parse use-case name, does not follow conventions:"+clmnmlusecase )

     if ( sim_year_range == "1850-2000" ): actual_year_range = "1849-2006"
     else:                                 actual_year_range = sim_year_range
elif ( clmnmlusecase.endswith("_control") ):
          sim_year       = re.search( '^([0-9]+)_', clmnmlusecase ).group(1)
          if ( sim_year == None ): error( "Trouble finding sim_year from:"+clmnmlusecase )
          sim_year       = str(sim_year)
          sim_year_range = "constant"
          rcp            = histrcp
elif ( clmnmlusecase.endswith("_pd") or clmnmlusecase == "UNSET" ):
          sim_year       = "2000"   
          sim_year_range = "constant"
          rcp            = histrcp
else:
          error( "Can not parse use-case name:, does not follow conventions"+clmnmlusecase )

if ( rcp == histrcp ):
   pftdyntype = "hist"
else:
   pftdyntype = "rcp"+rcp

qoptionsbase   = " -options mask="+mask+",rcp="+rcp
   
qoptions       = qoptionsbase+",sim_year="+sim_year+",sim_year_range="+sim_year_range;
queryOpts      = " -onlyfiles -res "+clmres+clmusrdat+qoptions
queryOptsNousr = qoptions
queryOptsNavy  = " -res 0.33x0.33 "+qoptions

#
# If you are trying to cycle the forcing years you need to be careful about
# the number of years cycling over and taking leap years into account.
#
if ( options.cycle_forcing ):
    numyears = endyear - startyear + 1
    numfour = int(numyears/4)
    # If have three years or less (numfour = 0) just repeat first year  
    # unless first year is leap year then use next year.
    # Since just using one year that is not a leap year endyear is startyear
    if (numfour == 0):
      if (startyear % 4 == 0):
        startyear = startyear + 1

      endyear  = startyear
    else:
      endyear = startyear + numfour * 4 - 1

    alignyear = startyear

if plev>0: print "CLM Physics Version: "+options.clmphysvers

####### ANY OTHER LAST SETTINGS BEFORE CREATING DATASETS ################################

myrun_n     = options.myrun_n
myrun_units = options.myrun_units


#####  ENV XML CHANGES ##################################################################

if ( clmusrdatname != "" ):
   xmlchange_env_value( "CLM_USRDAT_NAME", clmusrdatname )

datm_mode= options.datm_mode
if(datm_mode == "CLM_QIAN" and endyear > 2004):
    endyear = 2004
if(datm_mode == "CLM1PT" or options.use_tower_yrs):
    xmlchange_env_value( "DATM_CLMNCEP_YR_START", str(startyear) )
    xmlchange_env_value( "DATM_CLMNCEP_YR_END",   str(endyear) )

xmlchange_env_value( "CLM_BLDNML_OPTS", "'-mask "+mask+"'" )

xmlchange_env_value( "MPILIB", "mpi-serial" )

############# BEGIN CREATE POINT DATASETS ###############################################


if plev>0: print("Making input files for the point (this may take a while if creating transient datasets)")

os.chdir(data_dir)
#make map grid file and atm to ocean map ############################################
if plev>0: print "Creating map file for a point with no ocean"
print "lat="+str(lat)
ptstr = str(lat)+","+str(lon)
if ( os.system( "which ncl" ) != 0 ): error( "ncl is NOT in path" )  # check for ncl
system(mkmapdat_dir+"/mknoocnmap.pl -p "+ptstr+" -name "+clmres+" > "+data_dir+"/mknoocnmap.log")
stdout        = os.popen( "ls -1t1 "+mkmapdat_dir+"/map_"+clmres+"_noocean_to_"+clmres+"_"+"nomask_aave_da_*.nc | head -1" );
mapfile       = stdout.read().rstrip( );
if ( not os.path.exists( mapfile) ): error( "mapfile does NOT exist" )
print "mapfile="+mapfile+"\n";
cmd           = "ls -1t1 "+mkmapgrd_dir+"/SCRIPgrid_"+clmres+"_nomask_c*.nc | head -1"
print "cmd="+cmd
stdout        = os.popen( cmd )
scripgridfile = stdout.read().rstrip( );
print "scripgridfile="+scripgridfile+"\n";
if ( not os.path.exists( scripgridfile) ): error( "scripgridfile does NOT exist" )

#make domain file needed by datm ####################################################
if plev>0: print "Creating data domain"
cmd = gen_dom_dir+"/gen_domain -m "+mapfile+" -o "+clmmask+" -l "+clmres+" -c 'Running gen_domain from PTCLM' > "+data_dir+"/gen_domain.log"
system(cmd);
cmd        = "ls -1t1 domain.lnd."+clmres+"_"+clmmask+"*.nc | head -1"
print "cmd="+cmd
stdout     = os.popen( cmd )
domainfile = stdout.read().rstrip( );
if ( not os.path.exists( domainfile) ): error( "domainfile does NOT exist" )


#make surface data and dynpft #######################################################
if plev>0: print "\n\nRe-create surface dataset:\t"
if ( sim_year_range == "constant" ):
   mksrfyears = sim_year
else:
   mksrfyears = sim_year_range

#make mapping files needed for mksurfdata_map #######################################
stdout = os.popen( "date +%y%m%d" );
sdate  = stdout.read().rstrip( );
mapdir = data_dir
# mkmapdata.sh remembers where it is (although it starts over for a new date)
if plev>0: print "\n\nRe-create mapping files for surface dataset:"
cmd = mkmapdat_dir+"/mkmapdata.sh --gridfile "+scripgridfile+" --res "+clmres+" --gridtype regional --phys "+options.clmphysvers+" > "+data_dir+"/mkmapdata.log";
system(cmd);
# --- use site-level data for mksurfdata_map when available ----
#PFT information for the site
if (options.pftgrid == False):
    if plev>0: print "Replacing PFT information in surface data file"
    os.chdir(ptclm_dir+"/PTCLM_sitedata")
    AFdatareader = csv.reader(open(pftdata, "rb"))
    os.chdir(data_dir)
    pft_frac=[0,0,0,0,0]
    pft_code=[0,0,0,0,0]
    found=0
    for row in AFdatareader:
        if plev>1: print " site = %9s" % row[0]
        if row[0] == mysite:
            found=1
            output=open("./tempsitePFT.txt","w")      
            output.write(' '.join(row[1:11]))
            output.close()
            for thispft in range(0,5):
                pft_frac[thispft]=float(row[1+2*thispft])
                pft_code[thispft]=int(row[2+2*thispft])
    if ( found == 0 ):
       error( "Did NOT find input sitename:"+mysite+" in pftdata:"+pftdata+ \
              " run with pftgrid instead")
    # Find index of first zero
    for i in range(0,len(pft_frac)):
       if ( pft_frac[i] == 0.0 ):
          nzero = i
          break
    pftopts=" -pft_frc \""+str(pft_frac[0:nzero])+'"' \
               " -pft_idx \""+str(pft_code[0:nzero])+'"'
else: 
    pftopts=""
   
#Read in the soil conditions for the site #######################################
if (options.soilgrid == False):

    #soil information
    os.chdir(ptclm_dir+"/PTCLM_sitedata")
    if plev>0: print "Replacing soil information in surface data file"
    AFdatareader = csv.reader(open(soildata, "rb"))
    os.chdir(data_dir)
    found=0
    for row in AFdatareader:
        if plev>1: print " site = %9s" % row[0]
        if row[0] == mysite:
            found=1
            output=open("./tempsitesoil.txt","w")
            output.write(' '.join(row[1:7]))
            output.close()
            # The first three items are NOT used
            soil_depth = float(row[1])  # This is ignored
            n_layers   = int(row[2])    # This is ignored
            layer_depth = float(row[3]) # This is ignored
            sandpct     = float(row[4])
            claypct     = float(row[5])
    if ( found == 0 ):
       error( "Did NOT find input sitename:"+mysite+" in soildata:"+soildata+ \
              " run with soilgrid instead")
    if plev>0: print " sandpct="+str(sandpct)+" claypct="+str(claypct)
    soilopts=" -soil_cly "+str(claypct)+" -soil_snd "+str(sandpct)
else: soilopts=""
#----- create dynamic pft input file --------------- ############################
if (options.pftgrid == False) and (sim_year_range != "constant"):

    if plev>0: print "Creating site-specific dynamics PFTs and harvesting"

    pftdyn_site_filename = ptclm_dir + "/PTCLM_sitedata/" + \
                           mysite + "_dynpftdata.txt"

    # only set dynpft file if the file exists
    if ( os.path.exists( pftdyn_site_filename ) ):
       if plev>0: print "Transition PFT file exists, so using it for changes in PFT"
           # Convert the file from transition years format to mksurfdata_map pftdyn format
       cnv = ptclm_dir + \
             "/PTCLM_sitedata/cnvrt_trnsyrs2_pftdyntxtfile.pl " + \
             pftdyn_site_filename+" "+sim_year_range
       pftdynoutfile = data_dir+"/pftdyn_"+mysite+".txt"
       system( cnv+" > "+pftdynoutfile )
       dynpftopts = " -dynpft "+pftdynoutfile
    else:
       if plev>0: print "Transition PFT file did NOT exist, so proceeding with constant PFT"
       dynpftopts = ""
           
else: 
    dynpftopts = ""

    # Now run mksurfdata_map  ###########################################################
    mksurfopts = "-res usrspec -usr_gname "+clmres+" -usr_gdate "+sdate+ \
                 " -usr_mapdir "+mapdir+" -dinlc "+cesm_input+" -y "+mksrfyears+ \
                 " -rcp "+rcp+soilopts+pftopts+dynpftopts+" "+options.mksurfdata_opts
    system(clm_tools+"/"+options.clmphysvers+"/mksurfdata_map/mksurfdata.pl "+mksurfopts+" > "+data_dir+"/mksurfdata_map.log")

    stdout  = os.popen( "ls -1t1 "+data_dir+"/surfdata_"+clmres+"_simyr"+sim_year+"_*.nc | head -1" );
    surffile= stdout.read().rstrip( );
    stdout  = os.popen( "ls -1t1 "+data_dir+"/surfdata_"+clmres+"_simyr"+sim_year+"_*.log | head -1" );
    logfile = stdout.read().rstrip( );
    if ( not os.path.exists( surffile ) ): error( "surface file does NOT exist"     )
    if ( not os.path.exists( logfile  ) ): error( "surface log file does NOT exist" )
    if ( sim_year_range != "constant" ):
       stdout     = os.popen( "ls -1t1 "+data_dir+"/surfdata.pftdyn_"+clmres+"_"+pftdyntype+"_simyr"+actual_sim_year_range+"_"+"_*.nc | head -1" );
       pftdynfile = stdout.read().rstrip( );
       if ( not os.path.exists( pftdynfile ) ): error( "pftdynfile file does NOT exist" )
    # rename files with clm version in the filename
    newsurffile = "surfdata_"+clmres+"_simyr"+sim_year+"_"+options.clmphysvers+"_c"+sdate+".nc"
    newlogfile  = "surfdata_"+clmres+"_simyr"+sim_year+"_"+options.clmphysvers+"_c"+sdate+".log"
    system("/bin/mv -f "+surffile+" "+newsurffile )
    system("/bin/mv -f "+logfile+" "+newlogfile   )
    surffile    = data_dir+"/"+newsurffile
    if (sim_year_range != "constant"):
        newpftdynfile = "surfdata.pftdyn"+clmres+"_"+pftdyntype+"_simyr"+actual_sim_year_range+"_"+options.clmphysvers+"_c"+sdate+".nc"
        system("/bin/mv -f "+pftdynfile+" "+newpftdynfile )
        pftdynfile = data_dir+"/"+newpftdynfile



   
####### END CREATE POINT DATASETS #######################################################


###### SET ENV_RUN.XML VALUES ###########################################################
   
os.chdir(data_dir)
xmlchange_env_value( "ATM_DOMAIN_PATH", data_dir   )
xmlchange_env_value( "LND_DOMAIN_PATH", data_dir   )
xmlchange_env_value( "ATM_DOMAIN_FILE", domainfile )
xmlchange_env_value( "LND_DOMAIN_FILE", domainfile )

xmlchange_env_value( "CALENDAR",        "GREGORIAN" )
xmlchange_env_value( "DOUT_S",          "FALSE" )
hist_nhtfrq = 0
hist_mfilt  = 1200

atm_ncpl = int((60 // timestep) * 24)
xmlchange_env_value(    "ATM_NCPL", str(atm_ncpl) )
xmlchange_env_value( "RUN_STARTDATE", str(alignyear)+"-01-01" )
xmlchange_env_value( "DATM_CLMNCEP_YR_ALIGN", str(alignyear) )

#default simulation length for different types of runs
if (  myrun_units != defmyrun_units ):
   xmlchange_env_value( "STOP_OPTION", myrun_units )
   xmlchange_env_value( "REST_OPTION", str(myrun_units) )
if (  myrun_n != defmyrun_n ):
   xmlchange_env_value( "STOP_N",      str(myrun_n) )
   rest_n = max( 1, int(myrun_n) // 5 )
   xmlchange_env_value( "REST_N",      str(rest_n)     )

if plev>0: print "Number of simulation "+myrun_units+" to run:\t\t\t\t"+str(myrun_n)

xmlchange_env_value( "DIN_LOC_ROOT", cesm_input   )


####  NAMELIST DEFAULTS FILE MODIFICATIONS ##############################################
datm_dir = data_dir+"/CLM1PT_data"
if ( os.path.isdir(datm_dir) ):
   write_datm_namelistdefaults_file( datm_dir )

####  SET NAMELIST OPTIONS ##############################################################
output = open("user_nl_clm",'w')
output.write(   " fsurdat = '"+surffile+"'\n" )
if (sim_year_range != "constant"):
   output.write(   " fpftdyn = "+pftdynfile+"\n" )
output.write(   " hist_nhtfrq = "+str(hist_nhtfrq)+"\n" )
output.write(   " hist_mfilt  = "+str(hist_mfilt)+"\n" )
if(options.namelist != " "):
   output.write(options.namelist+"\n")
output.close()
if plev>1: os.system( "/bin/cat user_nl_clm" )

###### END SET Spinup and ENV_RUN.XML VALUES ############################################

if plev>0: print "Data created successfully in "+data_dir+"\n"

###   END PTCLM SCRIPT ####################################################################

