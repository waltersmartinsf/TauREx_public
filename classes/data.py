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
import library.library_general as libgen



class data(object):

#initialisation
    def __init__(self,params):
        self.params = params
        self.KBOLTZ=1.380648813e-23
        
        #reading in spectrum data to be fitted
        self.spectrum = self.readfile(params.in_spectrum_file)
        self.nwave = len(self.spectrum[:,0])
        self.wavegrid = self.spectrum[:,0]
        if params.fit_manual_waverange:
            self.specgrid,self.dlamb_grid = self.get_specgrid(R=self.params.fit_spec_res,
                                          lambda_min=self.params.fit_wavemin,lambda_max=self.params.fit_wavemax)
        else:
            self.specgrid,self.dlamb_grid = self.get_specgrid(R=self.params.fit_spec_res,
                                          lambda_min=self.wavegrid[0],lambda_max=self.wavegrid[-1])
        self.nspecgrid = len(self.specgrid)

        #calculating atmospheric scale height
        self.scaleheight = self.get_scaleheight()

        #reading in atmospheric profile file
        #or generating it from parameter file values
        #pta = pressure, temp, alt
        #X = mixing ratios of molecules
        if self.params.in_use_ATMfile:
            self.pta,self.X = self.readATMfile()
            self.nlayers = len(self.pta[:,0])
            self.ngas = len(self.X[:,0])
        else:
            self.nlayers = self.params.tp_atm_levels
            self.ngas    = self.params.tp_num_gas
            self.pta     = self.setup_pta_grid()
            self.X       = zeros((self.ngas,self.nlayers))
            self.X      += 1e-5  #setting up initial mixing ratios


        #calculating densities
        self.rho = (self.pta[:,0])/(self.KBOLTZ*self.pta[:,1])
        self.rho_tot = sum(self.rho)

        #setting up dictionary with atmosphere parameters
        self.atmosphere = self.init_atmosphere()
        
        #reading in absorption coefficient data 
#         self.sigma_array = self.readABSfiles()
        self.sigma_dict = self.build_sigma_dic()
        
        

        #reading in other files if specified in parameter file
        if params.in_include_rad:
            self.rad = self.readfile(self.params_in_rad_file,INTERPOLATE=True)
        if params.in_include_cia:
            self.cia = self.readfile(self.params.in_cia_file,INTERPOLATE=True)
        if params.in_include_cld:
            self.cld = self.readfile(self.params.in_cld_file,INTERPOLATE=True) 
            


#basic class methods and overloading
    def list(self,name=None):
        if name is None:
            return dir(self)[2:-1]
        else:
            lst = dir(self)
            return filter(lambda k: name in k, lst)
        
    def __getattribute__(self,name):
        return object.__getattribute__(self, name)
    
    def __getitem__(self,name):
        return self.__dict__[name] 

    def reset(self,params):
    #allows to reset the original instance to reflect changes in the data instance
    #this avoids an initialisation of a separate instance.
        self.__init__(params)

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

    def get_scaleheight(self,T_aver=None,surf_g=None,mmw=None):
        #compute scaleheight of atmosphere
        if T_aver is None:
            T_aver = self.params.planet_temp
        if surf_g is None:
            surf_g = self.params.planet_grav
        if mmw is None:
            mmw = self.params.planet_mu

        return (self.KBOLTZ*T_aver)/(mmw*surf_g)

    def get_specgrid(self,R=5000,lambda_min=0.1,lambda_max=20.0):
    #generating wavelength grid with uniform binning in log(lambda)
    #lambda min and max are in microns, R is the spectral resolution
    #R = lambda/delta_lamdba
        specgrid = []
        delta_lambda =[]

        specgrid.append(lambda_min)
        run = True
        i=1
        while run:
            dlam= specgrid[i-1]/R
            specgrid.append(specgrid[i-1]+dlam)
            delta_lambda.append(dlam)

            if specgrid[i] >= lambda_max:
                run=False
            i+=1

        # figure()
        # plot(specgrid)
        # figure()
        # plot(delta_lambda)
        # show()
        # exit()

        return np.asarray(specgrid),np.asarray(delta_lambda)


    def setup_pta_grid(self):
    #generating atmospheric Pressure, Temperature, Altitude (PTA)
    #grid if not read in from ATM file
        MAX_P    = self.params.tp_max_pres
        N_SCALE  = self.params.tp_num_scale
        N_LAYERS = self.params.tp_atm_levels

        max_z    = N_SCALE * self.scaleheight
#         dz       = max_z / N_LAYERS

        #generatinng altitude-pressure array
        PTA_arr = zeros((N_LAYERS,3))
        PTA_arr[:,2] = linspace(0,max_z,num=N_LAYERS)
        PTA_arr[:,0] = MAX_P * exp(-PTA_arr[:,2]/self.scaleheight)
        PTA_arr[:,1] = self.params.planet_temp

        return PTA_arr

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


    def set_ABSfile(self,path=None,filelist=None,interpolate = False,temperature=None):
    #manually overwrites absorption coefficients from new file
    #input path needs to be given and list of filename strings
        if path is None:
            extpath = self.params.in_abs_path
        if filelist is None:
            raise IOError('No input ABS file specified')
        if temperature is None:
            temperature = self.params.planet_temp
        
        sigma_array,self.specgrid = self.readABSfiles(extpath=path,extfilelist=filelist, interpolate2grid=interpolate,outputwavegrid=True)
        self.sigma_dict = {}
        self.sigma_dict['tempgrid'] = [int(temperature)]
        self.sigma_dict[int(temperature)] = sigma_array
        self.nspecgrid = len(self.specgrid)



    def build_sigma_dic(self,tempstep=50):
        #building temperature dependent sigma_array
        
        try:
            mollist = [self.params.planet_molec.item()] #necessary for 0d numpy arrays
        except ValueError:
            mollist = self.params.planet_molec
        
#         print self.params.planet_molec
        
        tempmin = []
        tempmax = []
                
        moldict = {}
        
        
        for molecule in mollist:
            moldict[molecule] ={}
            
            absfiles, templist = libgen.find_absfiles(self.params.in_abs_path,molecule)
            tempmax.append(np.max(templist))
            tempmin.append(np.min(templist))
            
            sigtmp = self.readABSfiles(extfilelist=absfiles, extpath=self.params.in_abs_path, interpolate2grid=True, outputwavegrid = False)
            
            sigshape = np.shape(sigtmp)
            
            moldict[molecule]['sigma'] = sigtmp
            moldict[molecule]['templist'] = templist
            moldict[molecule]['tempmin'] = tempmin
            moldict[molecule]['tempmax'] = tempmax
            
            
#             figure()
#             plot(np.transpose(sigtmp))
#             show()

        #setting up new temperature grid
        temp_totmin = np.max(tempmin)
        temp_totmax = np.min(tempmax)
        tempgrid = [i for i in range(int(temp_totmin),int(temp_totmax),int(tempstep))]
        tempgrid.append(int(temp_totmax))
        moldict['tempgrid'] = tempgrid 
        
#         print temp_totmax, temp_totmin, tempgrid
        
        #interpolating absorption cross sections to new temperature grid
        for molecule in mollist:
            interpsigma = zeros((len(tempgrid),sigshape[1]))
            
            for i in range(sigshape[1]):
                interpsigma[:,i] = np.interp(tempgrid,moldict[molecule]['templist'],moldict[molecule]['sigma'][:,i]) #linear interpolation. to be changed with hill et al method 
            
            moldict[molecule]['interpsigma'] = interpsigma
            
#             print np.shape(interpsigma)
#             figure()
#             plot(np.transpose(interpsigma))

        #building final sigma_array dictionary
        sigma_dict = {}
        sigma_dict['tempgrid'] = tempgrid
        for i in range(len(tempgrid)):
            sigma_dict[tempgrid[i]] = {}
            
            sigma_array = zeros((len(mollist),sigshape[1]))
            j = 0
            for molecule in mollist:
                sigma_array[j,:] = moldict[molecule]['interpsigma'][i,:]
                j += 1
            sigma_dict[tempgrid[i]] = sigma_array
            
#             print tempgrid[i], type(tempgrid[i])
#             figure()
#             plot(np.transpose(sigma_dict[tempgrid[i]]))
#             show() 
            
        
#         figure()
#         plot(np.transpose(sigma_dict[600][0,:]),'b')
#         plot(np.transpose(sigma_dict[1600][0,:]),'r')
#         
#         show()

        return sigma_dict



    def readATMfile(self):
    #reads in .atm file
        try:
            OUT = loadtxt(self.params.in_atm_file)
        except ValueError:
            OUT = loadtxt(self.params.in_atm_file,comments='*',skiprows=10)
        OUT[:,2] *= 1000. #converting from km to m
        
        OUT = OUT[argsort(OUT[:,2]),:]
        
        return OUT[:,0:3],transpose(OUT[:,3:])
    
    
    
    def readABSfiles(self,extfilelist=None, extpath= None,interpolate2grid=True,outputwavegrid=False):
    #reading in all absorption coefficient files and interpolating them to wavelength grid
    #
    # if filename = None, the absorption coefficient files will be read from the parameter file
    # if filename = [ascii list], absorption coefficient files will be read from user specified list
    # if outputwavegrid = True, it takes the first column of the ABS file and outputs as separate wavelength grid


        if extfilelist is None:
            #reading in list of abs files from parameter file
            if isinstance(self.params.in_abs_files,str):
                absfiles = genfromtxt(StringIO(self.params.in_abs_files),delimiter=",",dtype="S")
                try:
                    abslist = [absfiles.item()] #necessary for 0d numpy arrays
                except ValueError:
                    abslist = absfiles
            else:
                abslist = self.params.in_abs_files

            #checking if number of gasses in parameters file is consistent with gass columns in atm file
            if self.params.in_use_ATMfile and len(abslist) != self.ngas:
                print len(abslist)
                print self.ngas
                raise IOError('Number of gasses in .atm file incompatible with number of .abs files specified in parameters file')
                exit()

            OUT, WAVE = self.__readABSfiles_sub(path=self.params.in_abs_path,filelist=abslist, interpolate2grid=interpolate2grid,num=self.ngas)

        else:
            OUT, WAVE = self.__readABSfiles_sub(path=extpath,filelist=extfilelist, interpolate2grid=interpolate2grid,num=len(extfilelist))

        if outputwavegrid:
            return OUT, WAVE
        else:
            return OUT
        

    def __readABSfiles_sub(self,path, filelist, interpolate2grid,num):
        if interpolate2grid:
            OUT = zeros((num,self.nspecgrid))
            WAVE = transpose(self.readfile(path+filelist[0],INTERPOLATE=True)[:,0])
        else:
            tmp = self.readfile(path+filelist[0],INTERPOLATE=False)
            ABSsize = len(tmp[:,0])
            OUT = zeros((num,ABSsize))
            WAVE = transpose(tmp[:,0])

        for i in range(num):
            # print filelist[i]
            OUT[i,:] = transpose(self.readfile(path+filelist[i],INTERPOLATE=interpolate2grid)[:,1])* 1e-4 #converting cm^2 to m^2

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

        #interpolating to specgrid
        if INTERPOLATE:
#             interpflux = interp1d(OUT[:,0],OUT[:,1],axis=0,kind='cubic')(self.wavegrid)
            interpflux = interp(self.specgrid,OUT[:,0],OUT[:,1])
#             print interpflux
            OUT = transpose(vstack((self.specgrid,interpflux)))
        # print 'ble',np.shape(OUT)
#         plot(OUT[:,0], OUT[:,1], c='r')
#         show()
        return OUT

        