#! /usr/bin/python -W ignore

###########################################################
# create_spectrum - running minimal version of TauRex to 
# create transmission (and later emission) spectra from 
# parameter file values. 
#
# Requirements: -python libraries: pylab, numpy, ConfigParser 
#             [these are the minimum requirements]
#
# Additional requirements: pymc
#
# Inputs: minimal or normal parameter file
#
# Outputs: spectrum.dat
#
# To Run: 
# ./create_spectrum.py [-p exonest.par] 
#
# Modification History:
#   - v1.0 : first definition, Ingo Waldmann, June 2014      
#       
###########################################################


#loading libraries     
import sys, os, optparse, time
import numpy as np #nummerical array library 
import pylab as pl#science and plotting library for python
from ConfigParser import SafeConfigParser

#loading classes
sys.path.append('./classes')
sys.path.append('./library')

import parameters,emission,transmission,fitting,atmosphere,data,preselector
from parameters import *
from emission import *
from transmission import *
from fitting import *
from atmosphere import *
from data import *


#loading libraries
import library_emission, library_transmission, library_general
from library_emission import *
from library_transmission import *
from library_general import *


class create_spectrum(object):
    '''
    Create_spectrum class allows you to generate transmission/emission forward spectra with custom TP-profiles.
    Several support functions exist like plotting and saving to ascii. 
    create_spectrum.py can be run like usually from the command line: python create_spectrum.py [options]
    but can also be imported to other codes as library. This allows EChOSim, TauNet, etc to have direct 
    access to TauREx forward spectra. 
    '''

    def __init__(self,options, params=None):
        
        self.options = options
        if params is None:
            #initialising parameters object
            self.params = parameters(options.param_filename)
        else:
            self.params = params

        # set model resolution to 1000
        self.params.gen_spec_res = 1000
        self.params.gen_manual_waverange = True

        #initialising data object
        self.dataob = data(self.params)

        #initialising TP profile object
        self.atmosphereob = atmosphere(self.dataob)
        
        #set forward model
        if self.params.gen_type == 'transmission':
            self.fmob = transmission(self.atmosphereob)
        elif self.params.gen_type == 'emission':
            self.fmob = emission(self.atmosphereob)
        
        #TP-profile stuff
        self.MAX_P = self.atmosphereob.P[0]
        self.MIN_P = self.atmosphereob.P[-1]
    
        
        #get grids
        self.wavegrid, self.dlamb_grid = self.dataob.get_specgrid(R=int(options.resolution),lambda_min=self.params.gen_wavemin,lambda_max=self.params.gen_wavemax)
        self.spec_bin_grid, self.spec_bin_grid_idx = self.dataob.get_specbingrid(self.wavegrid, self.dataob.specgrid)
   
        
    def generate_spectrum(self):
        #run forward model and bin it down 
        model = self.fmob.model()
        model_binned = [model[self.spec_bin_grid_idx == i].mean() for i in xrange(1,len(self.spec_bin_grid))]
        
        #saving binned model to array: wavelength, flux, errorbar 
        self.spectrum = np.zeros((len(self.wavegrid),3))
        self.spectrum[:,0] = self.wavegrid
        self.spectrum[:,1] = model_binned
        self.spectrum[:,2] += float(self.options.error) * 1e-6

        #add noise to flux values
        if int(options.noise) == 1:
            self.spectrum[:,1] += np.random.normal(0, float(self.options.error) * 1e-6, len(self.wavegrid))
        
        return self.spectrum
    
    
    def generate_tp_profile_1(self,Pnodes, Tnodes,smooth_window=5):
        #generates ad-hoc TP profile given pressure and temperature nodes
    
        TP = np.interp((np.log(self.atmosphereob.P[::-1])), np.log(Pnodes[::-1]), Tnodes[::-1])
        #smoothing T-P profile
        wsize = self.atmosphereob.nlayers*(smooth_window/100.0)
        if (wsize %2 == 0):
            wsize += 1
        TP_smooth = self.movingaverage(TP,wsize)
        border = np.int((len(TP) - len(TP_smooth))/2)
        
        #set atmosphere object 
        self.fmob.atmosphere.T = TP[::-1]
        self.fmob.atmosphere.T[border:-border] = TP_smooth[::-1]   
            
        
    def generate_tp_profile_2(self,tp_params,tp_type='2point'):
        #generates tp profile from functions available in atmosphere class
        self.fmob.atmosphere.set_TP_profile(profile=tp_type)
        self.fmob.atmosphere.T = self.atmosphereob.TP_profile(fit_params=tp_params)
      
        
    def save_tp_profile(self,filename='TP_profile.dat'):
        #saves TP profile currently held in atmosphere object 
        out = np.zeros((len(self.fmob.atmosphere.T),2))
        out[:,0] = self.fmob.atmosphere.T
        out[:,1] = self.fmob.atmosphere.P
        np.savetxt(filename,out)
        
    def save_spectrum(self,filename='spectrum.dat'):
        #saves spectrum to ascii file 
        np.savetxt(filename, self.spectrum)
        
    def plot_tp_profile(self):
        #plotting TP-profile
        T = self.fmob.atmosphere.T
        P = self.fmob.atmosphere.P
        pl.figure()
        pl.plot(T, P)
        pl.xlim(np.min(T)-np.min(T)*0.1,np.max(T)+np.max(T)*0.1)
        pl.yscale('log')
        pl.xlabel('Temperature')
        pl.ylabel('Pressure (Pa)')
        pl.gca().invert_yaxis()
    
    def plot_spectrum(self):
        #plotting spectrum
        pl.figure()
        pl.errorbar(self.spectrum[:,0],self.spectrum[:,1],self.spectrum[:,2])
        pl.xlabel(r'Wavelength $\mu$m')
        if self.params.gen_type == 'transmission':
            pl.ylabel(r'$(R_{p}/R_{\ast})^2$')
        elif self.params.gen_type == 'emission':
            pl.ylabel(r'$F_{p}/F_{\ast}$')
        
        
    def movingaverage(self,values,window):
        weigths = np.repeat(1.0, window)/window
        smas = np.convolve(values, weigths, 'valid')
        return smas #smas2[::-1] # as a numpy array



#gets called when running from command line 
if __name__ == '__main__':
    
    parser = optparse.OptionParser()
    parser.add_option('-p', '--parfile',
                      dest="param_filename",
                      default="exonest.par",
    )
    parser.add_option('-r', '--res',
                      dest="resolution",
                      default=1000,
    )
    parser.add_option('-n', '--noise',
                      dest="noise",
                      default=0,
    )
    parser.add_option('-e', '--error',
                      dest="error",
                      default=50,
    )
    parser.add_option('-T', '--T_profile',
                      dest="tp_profile",
                      default=False,
                      action="store_true",
    )
    parser.add_option('-v', '--verbose',
                      dest="verbose",
                      default=True,
                      action="store_true",
    )
    parser.add_option('-s', '--spectrum_filename',
                      dest='specfilename',
                      default='spectrum.dat'
    )
    parser.add_option('-t', '--tp_filename',
                      dest='tpfilename',
                      default='TP_profile.dat'
    )
    options, remainder = parser.parse_args()
    
    
    #loading object
    createob = create_spectrum(options)
    #setup TP profile 
    if options.tp_profile:
        Pnodes = [createob.MAX_P,1e4, 100.0,createob.MIN_P]
        Tnodes = [2200,2200, 1700,1700]
        createob.generate_tp_profile_1(Pnodes, Tnodes)
    #generating spectrum
    createob.generate_spectrum()
    #saving spectrum
    createob.save_spectrum(filename=options.specfilename)
    #saving TP profile
    if options.tp_profile:
        createob.save_tp_profile(filename=options.tpfilename)
    
    if options.verbose:
        createob.plot_spectrum()
        if options.tp_profile:
            createob.plot_tp_profile()
        pl.show()