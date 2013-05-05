################################################
#class parameters 
#Parse parameter file eg. 'exonest.par' and initialise  
#parameters for run
################################################
from ConfigParser import SafeConfigParser

class parameters(object):
#instantiation
    def __init__(self, parfile):
        '''
        a parameter file is parsed and initial parameter values are set.  
        to add a new parameter edit this file and the input .par file.
        V1.0  - Definition - C. MacTavish, Apr 2012
        '''
        
        #conversion constants
        RSOL  = 6.955e8         #stellar radius to m
        RJUP  = 6.9911e7        #jupiter radius to m
        REARTH= 6.371e3         #earth radius to m
        AU    = 1.49e11         #semi-major axis (AU) to m
        AMU   = 1.660538921e-27 #atomic mass to kg
        
        #config file parser
        parser = SafeConfigParser()
        parser.read(parfile)
        
        self.verbose               = parser.getboolean('General', 'verbose')
        self.trans_cpp             = parser.getboolean('General', 'trans_cpp')
        
        self.in_spectrum_file      = parser.get('Input','spectrum_file')
        self.in_atm_file           = parser.get('Input','atm_file')
        self.in_abs_path           = parser.get('Input','abs_path')
        self.in_abs_files          = parser.get('Input','abs_files')
        
        self.in_include_rad        = parser.getboolean('Input','include_rad')
        self.in_rad_file           = parser.get('Input','rad_file')
        self.in_include_cia        = parser.getboolean('Input','include_cia')
        self.in_cia_file           = parser.get('Input','cia_file')  
        self.in_include_cld        = parser.getboolean('Input','include_cld')
        self.in_cld_file           = parser.get('Input','cld_file')
        
        self.out_path              = parser.get('Output','path')
        self.out_file              = parser.get('Output','file_name')
        
        self.star_radius           = parser.getfloat('Star', 'radius')    *RSOL
        
        self.planet_radius         = parser.getfloat('Planet', 'radius')  *RJUP
        self.planet_sma            = parser.getfloat('Planet', 'sma')     *AU
        self.planet_grav           = parser.getfloat('Planet', 'grav')
        self.planet_temp           = parser.getfloat('Planet', 'temp')
        self.planet_mu             = parser.getfloat('Planet', 'mu')      *AMU
        self.planet_molec          = parser.get('Planet','molec')
        
        self.tp_var_atm            = parser.getboolean('T-P profile','var_atm')
        self.tp_atm_levels         = parser.getfloat('T-P profile', 'atm_levels')
        self.tp_var_temp           = parser.getboolean('T-P profile', 'var_temp')
        self.tp_var_pres           = parser.getboolean('T-P profile', 'var_pres')
        self.tp_var_mix            = parser.getboolean('T-P profile', 'var_mix')
        
        self.fit_param_free        = parser.get('Fitting', 'param_free')
        
        self.mcmc_update_std       = parser.getboolean('MCMC','update_std')
        self.mcmc_data_std         = parser.getfloat('MCMC', 'data_std')
        self.mcmc_iter             = parser.getfloat('MCMC', 'iter')
        self.mcmc_burn             = parser.getfloat('MCMC','burn')
        self.mcmc_thin             = parser.getfloat('MCMC', 'thin')
        
        
        
        
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

