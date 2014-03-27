import numpy as np
import pylab as py
import sklearn.decomposition as sk
import glob,string, pickle,gzip

from classes.transmission import *
from classes.profile import *
from classes.data import *



def convert2microns(PATH, upcut=25):
#Function converting ExoMol cross section files in dir:PATH from wavenumbers to microns and sorting
#with ascending wavelength
#output: .abs files

    FILES = glob.glob(PATH)

    for f in FILES:
        if os.path.isfile(f[:-3]+'abs'):
            pass
        else:
            print 'converting: ', f
            tmp = np.loadtxt(f,dtype=np.float32)[1:,:]
            tmp[:,0] = 10000.0/tmp[:,0]
            idx = np.argsort(tmp[:,0],axis=-1)
            tmp2 = tmp[idx,:][np.where(tmp[idx,0] < upcut)]
            tmp2 = tmp2.astype(np.float32,copy=False)
            np.savetxt(f[:-3]+'abs',tmp2,fmt="%.6e,%.8e")


def generate_spectra_lib(PARAMS,PATH,OUTPATH,MIXING=[1e-6,1e-5,1e-4,1e-3,1e-2]):
    #Generates transmission spectra from cross section files for given mixing ratios
    #output: 2 column ascii files (.spec)

    #initiating objects needed
    dataob = data(PARAMS)
    dataob.add_molecule('H2', 2.0, 2.0e-9, 1.0001384, 0.85)

    profileob = profile(PARAMS, dataob)
    transob = transmission(PARAMS, dataob)

    #reading available cross section lists in PATH
    globlist = glob.glob(PATH+'*.abs')

    if os.path.isdir(OUTPATH) == False:
        os.mkdir(OUTPATH)

    for FILE in globlist:
        fname = string.rsplit(FILE,'/',1)[1] #splitting the name
        temp  = float(string.rsplit(fname,'_',2)[1][:-1]) #getting temperature from file name

        # print fname

        for mix in MIXING:
            X_in   = zeros((int(profileob.nlayers),int(profileob.ngas))) #setting up mixing ratio array
            X_in  += mix #setting mixing ratio
            rho_in = profileob.get_rho(T=temp) #calculating T-P profile

            dataob.set_ABSfile(path=PATH,filelist=[fname]) #reading in cross section file
            transob.reset(dataob) #resets transob to reflect changes in dataob

            #manually setting mixing ratio and T-P profile
            MODEL = transob.cpath_integral(rho=rho_in,X=X_in) #computing transmission
            np.savetxt(OUTPATH+fname[:-4]+'_'+str(mix)+'d.spec',np.column_stack((dataob.wavegrid,MODEL)))


def PCA(DATA0,PCnum):
#small wrapper doing PCA using sk module
    DATA = np.transpose(DATA0)
    # DATA = DATA0

    u,S,PC = np.linalg.svd(DATA)
    feature = np.transpose(PC)
    print 'no. of PCs: ', len(PC[:,0])
    feature = feature[:PCnum,:]
    return feature, PC



def generate_PCA_library(PATH,OUTPATH=False,comp_num=3):
    FILES = glob.glob(PATH)

    filename = FILES[0].rpartition('/')[-1]
    filenamesplit = filename.split('_')
    molname = filenamesplit[0]

    molnamelist = []
    molnamelist.append(molname)
    molnumlist = []
    mollenlist = []
    for f in FILES:
        if (f.rpartition('/')[-1]).split('_')[0] != molnamelist[-1]:
            molnamelist.append((f.rpartition('/')[-1]).split('_')[0])


    for i in range(len(molnamelist)):
        count = 0
        lencount = 0
        idx = 0
        for f in FILES:
            if (f.rpartition('/')[-1]).split('_')[0] == molnamelist[i]:
                count += 1
                if idx == 0:
                    lencount = np.shape(np.loadtxt(f))[0]
                    idx = 1

        mollenlist.append(lencount)
        molnumlist.append(count)

    OUTdic = {}
    for i in range(len(molnamelist)):
        DATA = np.zeros((mollenlist[i],molnumlist[i]))

        j=0
        for f in FILES:
            if (f.rpartition('/')[-1]).split('_')[0] == molnamelist[i]:
                tmp = np.loadtxt(f)
                DATA[:,j] = tmp[:,1]
                if j == 0:
                    wavegrid = tmp[:,0]
                    j += 1

        pca = sk.RandomizedPCA(n_components=comp_num)
        pca.fit(np.transpose(DATA))

        meanspec = np.mean(DATA,axis=1)

        normPCA = np.zeros((mollenlist[i],comp_num))
        for jj in range(comp_num):
            normPCA[:,jj] = (pca.components_[jj]-np.min(pca.components_[jj])) /np.max(pca.components_[jj])

        #add to OUTdic
        OUTdic[molnamelist[i]] = {}
        OUTdic[molnamelist[i]]['length']   = int(mollenlist[i])
        OUTdic[molnamelist[i]]['numbers']  = int(molnumlist[i])
        OUTdic[molnamelist[i]]['wavegrid'] = wavegrid
        OUTdic[molnamelist[i]]['data']     = DATA
        OUTdic[molnamelist[i]]['meanspec'] = meanspec
        OUTdic[molnamelist[i]]['PCA']      = {}
        OUTdic[molnamelist[i]]['PCA']['full'] = pca
        OUTdic[molnamelist[i]]['PCA']['norm'] = normPCA

        if OUTPATH != False:
            with gzip.GzipFile(OUTPATH+'spec_pcalib.pkl.zip','wb') as outhandle:
                pickle.dump(OUTdic,outhandle)

        return OUTdic