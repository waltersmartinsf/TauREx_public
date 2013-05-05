################################################
#class emission
#
# Calculates the emission radiative transfer 
# forward model
#
# Input: -
#
#
# Output: -  
#
#
# Modification History:
#   - v1.0 : first definition, Ingo Waldmann, Apr 2013 
#
################################################

#loading libraries     
import numpy
from numpy import *


class emission(object):





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