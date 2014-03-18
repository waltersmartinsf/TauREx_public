################################################
#class data
#
# Reads in all relevant data and performs pre-processing 
# such as sorting, grid-interpolations etc. 
#
# Input: -parameter object
#
#
# Output: -data object containing relevant data in dictionary 
#         format  
#
#
# Modification History:
#   - v1.0 : first definition, Ingo Waldmann, Apr 2013 
#
################################################

#loading libraries     
import numpy, pylab
from numpy import *
from pylab import *
from StringIO import StringIO
from scipy.interpolate import interp1d

class data(object):

#initialisation
    def __init__(self,params):
        self.params = params
        KBOLTZ=1.380648813e-23
        
        #reading in spectrum data to be fitted
        self.spectrum = self.readfile(params.in_spectrum_file)
        self.nwave = len(self.spectrum[:,0])
        self.wavegrid = self.spectrum[:,0]
        
        #reading in atmospheric profile file
        #pta = pressure, temp, alt
        #X = mixing ratios of molecules
        self.pta,self.X = self.readATMfile()
        self.nlayers = len(self.pta[:,0])
        self.ngas = len(self.X[:,0])
        
        #calculating densities
        self.rho = (self.pta[:,0])/(KBOLTZ*self.pta[:,1])
        self.rho_tot = sum(self.rho)
        
        #setting up dictionary with atmosphere parameters
        self.atmosphere = self.init_atmosphere()
        
        #reading in absorption coefficient data 
        self.sigma_array = self.readABSfiles()

        #reading in other files if specified in parameter file
        if params.in_include_rad == True:
            self.rad = self.readfile(self.params_in_rad_file,INTERPOLATE=True)
        if params.in_include_cia == True:
            self.cia = self.readfile(self.params.in_cia_file,INTERPOLATE=True)
        if params.in_include_cld == True:
            self.cld = self.readfile(self.params.in_cld_file,INTERPOLATE=True) 
            


#basic class methods and overloading
    def list(self,name=None):
        if name==None:
            return dir(self)[2:-1]
        else:
            lst = dir(self)
            return filter(lambda k: name in k, lst)
        
    def __getattribute__(self,name):
        return object.__getattribute__(self, name)
    
    def __getitem__(self,name):
        return self.__dict__[name] 



#class functions    
    def init_atmosphere(self, mu=0.0, def_mu=2.3):
    #initialising atmosphere dictionary
        ATM = {}
        ATM['mol'] = {}
        ATM['info'] = {}
        ATM['info']['def_mu']  = def_mu #default atmos 85% H2, 15% H2 --> mu~2.3
        ATM['info']['mu']      = mu
        ATM['info']['nmol']    = 0      #number of molecule index
        
        return ATM
    
    def add_molecule(self,NAME, WT, RAD, RIDX,FRAC):
    #adding a molecule to the atmosphere dictionary
        self.atmosphere['mol'][NAME] = {}
        self.atmosphere['mol'][NAME]['weight']  = WT   #relative molecular weight (amu)
        self.atmosphere['mol'][NAME]['radius']  = RAD  #molecular radius (m)
        self.atmosphere['mol'][NAME]['ridx']    = RIDX #refractive index
        self.atmosphere['mol'][NAME]['frac']    = FRAC #fraction of total composition
        self.atmosphere['info']['nmol']         += 1   #increasing molecule count
        #updating mean molecular weight of atmosphere
        self.atmosphere['info']['mu'] = self.get_mean_molweight()
        
    def get_mean_molweight(self):
    #returning mean molecular weight of atmosphere
        MMW = 0
        for m,M in enumerate(self.atmosphere['mol']):
            MMW += (self.atmosphere['mol'][M]['weight'] * self.atmosphere['mol'][M]['frac'])
        
        return MMW


    def set_ABSfile(self,path=None,filelist=None,interpolate = False):
    #manually overwrites absorption coefficients from new file
    #input path needs to be given and list of filename strings
        if path == None:
            extpath = self.params.in_abs_path
        if filelist == None:
            raise IOError('No input ABS file specified')

        self.sigma_array,self.wavegrid = self.readABSfiles(extpath=path,extfilelist=filelist,interpolate2data=interpolate,outputwavegrid=True)
        self.nwave = len(self.wavegrid)


    def readATMfile(self):
    #reads in .atm file
        try:
            OUT = loadtxt(self.params.in_atm_file)
        except ValueError:
            OUT = loadtxt(self.params.in_atm_file,comments='*',skiprows=10)
        OUT[:,2] *= 1000. #converting from km to m
        
        OUT = OUT[argsort(OUT[:,2]),:]
        
        return OUT[:,0:3],transpose(OUT[:,3:])
    
    
    
    def readABSfiles(self,extfilelist=None, extpath= None,interpolate2data=True,outputwavegrid=False):
    #reading in all absorption coefficient files and interpolating them to wavelength grid
    #
    # if filename = None, the absorption coefficient files will be read from the parameter file
    # if filename = [ascii list], absorption coefficient files will be read from user specified list
    # if outputwavegrid = True, it takes the first column of the ABS file and outputs as separate wavelength grid


        if extfilelist== None:
            #reading in list of abs files from parameter file
            absfiles = genfromtxt(StringIO(self.params.in_abs_files),delimiter=",",dtype="S")
            try:
                abslist = [absfiles.item()] #necessary for 0d numpy arrays
            except ValueError:
                abslist = absfiles

            #checking if number of gasses in parameters file is consistent with gass columns in atm file
            if len(abslist) != self.ngas:
                print len(abslist)
                print self.ngas
                raise IOError('Number of gasses in .atm file incompatible with number of .abs files specified in parameters file')
                exit()

            OUT, WAVE = self.__readABSfiles_sub(path=self.params.in_abs_path,filelist=abslist,interpolate2data=interpolate2data,num=self.ngas)

        else:
            OUT, WAVE = self.__readABSfiles_sub(path=extpath,filelist=extfilelist,interpolate2data=interpolate2data,num=len(extfilelist))

        if outputwavegrid == True:
            return OUT, WAVE
        else:
            return OUT
        

    def __readABSfiles_sub(self,path, filelist, interpolate2data,num):
        if interpolate2data == True:
            OUT = zeros((self.ngas,self.nwave))
            WAVE = transpose(self.readfile(path+filelist[0],INTERPOLATE=True)[:,0])
        else:
            tmp = self.readfile(path+filelist[0],INTERPOLATE=False)
            ABSsize = len(tmp[:,1])
            OUT = zeros((num,ABSsize))
            WAVE = transpose(tmp[:,0])

        for i in range(num):
            OUT[i,:] = transpose(self.readfile(path+filelist[i],INTERPOLATE=interpolate2data)[:,1])* 1e-4 #converting cm^2 to m^2

        return OUT, WAVE


    def readfile(self,NAME,INTERPOLATE=False):
    #reads in data file with columns wavelength and data
        try:
            OUT = loadtxt(NAME)
        except ValueError:
            OUT = loadtxt(NAME,delimiter=',')
        if len(OUT[:,0]) < len(OUT[0,:]):
            OUT = transpose(OUT)
        
        #sorting data along ascending first column    
        OUT = OUT[argsort(OUT[:,0]),:]
        
        
#         figure()
#         plot(OUT[:,0], OUT[:,1])
        
        #interpolating to wavelength grid of data
        if INTERPOLATE != False:
#             interpflux = interp1d(OUT[:,0],OUT[:,1],axis=0,kind='cubic')(self.wavegrid)
            interpflux = interp(self.wavegrid,OUT[:,0],OUT[:,1])
#             print interpflux
            OUT = transpose(vstack((self.wavegrid,interpflux)))
#         plot(OUT[:,0], OUT[:,1], c='r')
#         show()
        return OUT

        