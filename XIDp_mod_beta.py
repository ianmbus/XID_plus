
import numpy as np
import astropy
from astropy.io import fits
from astropy import wcs

#path for where stan models lie
import os
dirname, filename = os.path.split(os.path.abspath(__file__))
stan_path=dirname+'/stan_models/'
#this is a test

class prior(object):
    def __init__(self,im,nim,imphdu,imhdu):
        """class for SPIRE prior object. Initialise with map,uncertianty map and wcs"""
        #---for any bad pixels set map pixel to zero and uncertianty to 1----
        bad=np.logical_or(np.logical_or
                  (np.invert(np.isfinite(im)),
                   np.invert(np.isfinite(nim))),(nim == 0))
        if(bad.sum() >0):
            im[bad]=0.
            nim[bad]=1.
        self.im=im
        self.nim=nim
        self.imhdu=imhdu
        wcs_temp=wcs.WCS(self.imhdu)
        self.imphdu=imphdu
        self.imhdu=imhdu
        #add a boolean array 
        ind=np.empty_like(im,dtype=bool)
        ind[:]=True
        #get x and y pixel position for each position
        x_pix,y_pix=np.meshgrid(np.arange(0,wcs_temp._naxis1),np.arange(0,wcs_temp._naxis2))
        #now cut down and flatten maps (default is to use all pixels, running segment will change the values below to pixels within segment)
        self.sx_pix=x_pix[ind]
        self.sy_pix=y_pix[ind]
        self.snim=self.nim[ind]
        self.sim=self.im[ind]
        self.snpix=ind.sum()


    def prior_bkg(self,mu,sigma):
        """Add background prior ($\mu$) and uncertianty ($\sigma$). Assumes normal distribution"""
        self.bkg=(mu,sigma)

    def prior_cat(self,ra,dec,prior_cat_file,good_index=None,flux=None):
        """Input info for prior catalogue. Requires ra, dec and filename of prior cat. Checks sources in the prior list are within the boundaries of the map,
        and converts RA and DEC to pixel positions"""
        #get positions of sources in terms of pixels
        wcs_temp=wcs.WCS(self.imhdu)
        sx,sy=wcs_temp.wcs_world2pix(ra,dec,0)
        #check if sources are within map
        if hasattr(self, 'tile'):
            sgood=(ra > self.tile[0,0]-self.buffer_size) & (ra < self.tile[0,2]+self.buffer_size) & (dec > self.tile[1,0]-self.buffer_size) & (dec < self.tile[1,2]+self.buffer_size)#
        else:
            sgood=(sx > 0) & (sx < wcs_temp._naxis1) & (sy > 0) & (sy < wcs_temp._naxis2)
        #Redefine prior list so it only contains sources in the map
        self.sx=sx[sgood]
        self.sy=sy[sgood]
        self.sra=ra[sgood]
        self.sdec=dec[sgood]
        self.nsrc=sgood.sum()
        self.prior_cat=prior_cat_file
        if good_index != None:
            return sgood 
        if flux !=None:
            self.sflux=flux[sgood]


    def prior_cat_stack(self,ra,dec,prior_cat,good_index=None):
        """Input info for prior catalogue of sources being stacked. Requires ra, dec and filename of prior cat. Checks sources in the prior list are within the boundaries of the map,
        and converts RA and DEC to pixel positions"""
        #get positions of sources in terms of pixels
        wcs_temp=wcs.WCS(self.imhdu)
        sx,sy=wcs_temp.wcs_world2pix(ra,dec,0)
        #check if sources are within map 
        sgood=(ra > self.tile[0,0]-self.buffer_size) & (ra < self.tile[0,2]+self.buffer_size) & (dec > self.tile[1,0]-self.buffer_size) & (dec < self.tile[1,2]+self.buffer_size)# & np.isfinite(im250[np.rint(sx250).astype(int),np.rint(sy250).astype(int)])#this gives boolean array for cat

                

        #Redefine prior list so it only contains sources in the tile being fitted
        self.stack_sx=sx[sgood]
        self.stack_sy=sy[sgood]
        self.stack_sra=ra[sgood]
        self.stack_sdec=dec[sgood]
        self.sx=np.append(self.sx,sx[sgood])
        self.sy=np.append(self.sy,sy[sgood])
        self.sra=np.append(self.sra,ra[sgood])
        self.sdec=np.append(self.sdec,dec[sgood])
        self.nsrc=self.nsrc+sgood.sum()
        self.stack_nsrc=sgood.sum()
        if good_index != None:
            return sgood 
    
    def set_tile(self,tile,buffer_size):
        """Segment map to tile region described by tile and buffer_size"""
        #create polygon of tile (in format used by aplpy). Should be 2x4 array
        self.tile=tile
        #get vertices of polygon in terms of pixels
        wcs_temp=wcs.WCS(self.imhdu)

        tile_x,tile_y=wcs_temp.wcs_world2pix(tile[0,:],tile[1,:],0)

        x_pix,y_pix=np.meshgrid(np.arange(0,wcs_temp._naxis1),np.arange(0,wcs_temp._naxis2))

        npix=(x_pix < np.max(tile_x)) & (y_pix < np.max(tile_y)) & (y_pix >= np.min(tile_y)) & (x_pix >= np.min(tile_x))

        #now cut down and flatten maps
        self.sx_pix=x_pix[npix]
        self.sy_pix=y_pix[npix]
        self.snim=self.nim[npix]
        self.sim=self.im[npix]
        self.snpix=npix.sum()

        
        #store buffer size
        self.buffer_size=buffer_size


    def set_prf(self,prf,pindx,pindy):
        """Add prf array and corresponding x and y scales (in terms of pixels in map). \n Array should be an n x n array, where n is an odd number, and the centre of the prf is at the centre of the array"""
        self.prf=prf
        self.pindx=pindx
        self.pindy=pindy
        

    def get_pointing_matrix(self):
        """get the pointing matrix"""
        from scipy import interpolate        
        paxis1,paxis2=self.prf.shape

        amat_row=np.array([])
        amat_col=np.array([])
        amat_data=np.array([])
        
        #------Deal with PRF array----------
        centre=((paxis1-1)/2)
        #create pointing array
        for s in range(0,self.nsrc):



            #diff from centre of beam for each pixel in x
            dx = -np.rint(self.sx[s]).astype(long)+self.pindx[(paxis1-1.)/2]+self.sx_pix
            #diff from centre of beam for each pixel in y
            dy = -np.rint(self.sy[s]).astype(long)+self.pindy[(paxis2-1.)/2]+self.sy_pix
            #diff from each pixel in prf
            pindx=self.pindx+self.sx[s]-np.rint(self.sx[s]).astype(long)
            pindy=self.pindy+self.sy[s]-np.rint(self.sy[s]).astype(long)
            #diff from pixel centre
            px=self.sx[s]-np.rint(self.sx[s]).astype(long)+(paxis1-1.)/2.
            py=self.sy[s]-np.rint(self.sy[s]).astype(long)+(paxis2-1.)/2.
        
            good = (dx >= 0) & (dx < self.pindx[paxis1-1]) & (dy >= 0) & (dy < self.pindy[paxis2-1])
            ngood = good.sum()
            bad = np.asarray(good)==False
            nbad=bad.sum()
            if ngood > 0.5*self.pindx[-1]*self.pindy[-1]:
                ipx2,ipy2=np.meshgrid(pindx,pindy)
                atemp=interpolate.griddata((ipx2.ravel(),ipy2.ravel()),self.prf.ravel(), (dx[good],dy[good]), method='nearest')
                amat_data=np.append(amat_data,atemp)
                amat_row=np.append(amat_row,np.arange(0,self.snpix,dtype=long)[good])#what pixels the source contributes to
                amat_col=np.append(amat_col,np.full(ngood,s))#what source we are on

        #Add background contribution to pointing matrix: 
        #only contributes to pixels within tile
        snpix_bkg=self.snpix
        self.amat_data=np.append(amat_data,np.full(snpix_bkg,1))
        self.amat_row=np.append(amat_row,np.arange(0,self.snpix,dtype=long))
        self.amat_col=np.append(amat_col,np.full(snpix_bkg,s+1))

    def get_pointing_matrix_coo(self):
        """Get scipy coo version of pointing matrix. Useful for sparse matrix multiplication"""
        from scipy.sparse import coo_matrix
        self.A=coo_matrix((self.amat_data, (self.amat_row, self.amat_col)), shape=(self.snpix, self.nsrc+1))


def lstdrv_SPIRE_stan(SPIRE_250,SPIRE_350,SPIRE_500,chains=4,iter=1000):
    """Fit all three SPIRE maps using stan"""
    import pystan
    import pickle

    # define function to initialise flux values to one
    def initfun():
        return dict(src_f=np.ones(snsrc))
    #input data into a dictionary
        
    XID_data={'nsrc':SPIRE_250.nsrc,
          'npix_psw':SPIRE_250.snpix,
          'nnz_psw':SPIRE_250.amat_data.size,
          'db_psw':SPIRE_250.sim,
          'sigma_psw':SPIRE_250.snim,
          'bkg_prior_psw':SPIRE_250.bkg[0],
          'bkg_prior_sig_psw':SPIRE_250.bkg[1],
          'Val_psw':SPIRE_250.amat_data,
          'Row_psw': SPIRE_250.amat_row.astype(long),
          'Col_psw': SPIRE_250.amat_col.astype(long),
          'npix_pmw':SPIRE_350.snpix,
          'nnz_pmw':SPIRE_350.amat_data.size,
          'db_pmw':SPIRE_350.sim,
          'sigma_pmw':SPIRE_350.snim,
          'bkg_prior_pmw':SPIRE_350.bkg[0],
          'bkg_prior_sig_pmw':SPIRE_350.bkg[1],
          'Val_pmw':SPIRE_350.amat_data,
          'Row_pmw': SPIRE_350.amat_row.astype(long),
          'Col_pmw': SPIRE_350.amat_col.astype(long),
          'npix_plw':SPIRE_500.snpix,
          'nnz_plw':SPIRE_500.amat_data.size,
          'db_plw':SPIRE_500.sim,
          'sigma_plw':SPIRE_500.snim,
          'bkg_prior_plw':SPIRE_500.bkg[0],
          'bkg_prior_sig_plw':SPIRE_500.bkg[1],
          'Val_plw':SPIRE_500.amat_data,
          'Row_plw': SPIRE_500.amat_row.astype(long),
          'Col_plw': SPIRE_500.amat_col.astype(long)}
    
    #see if model has already been compiled. If not, compile and save it
    import os
    model_file=dirname+"/XID+SPIRE.pkl"
    try:
       with open(model_file,'rb') as f:
            # using the same model as before
            print("%s found. Reusing" % model_file)
            sm = pickle.load(f)
            fit = sm.sampling(data=XID_data,iter=iter,chains=chains)
    except IOError as e:
        print("%s not found. Compiling" % model_file)
        sm = pystan.StanModel(file=stan_path+'XID+SPIRE.stan')
        # save it to the file 'model.pkl' for later use
        with open(model_file, 'wb') as f:
            pickle.dump(sm, f)
        fit = sm.sampling(data=XID_data,iter=iter,chains=chains)
    #extract fit
    fit_data=fit.extract(permuted=False, inc_warmup=False)
    #return fit data
    return fit_data,chains,iter

def lstdrv_stan_highz(prior,chains=4,iter=1000):
    #
    import pystan
    import pickle

    # define function to initialise flux values to one
    def initfun():
        return dict(src_f=np.ones(prior.nsrc))
    #input data into a dictionary

    XID_data={'npix':prior.snpix,
          'nsrc':prior.nsrc,
          'nsrc_z':prior.stack_nsrc,
          'nnz':prior.amat_data.size,
          'db':prior.sim,
          'sigma':prior.snim,
          'bkg_prior':prior.bkg[0],
          'bkg_prior_sig':prior.bkg[1],
          'Val':prior.amat_data,
          'Row': prior.amat_row.astype(long),
          'Col': prior.amat_col.astype(long)}
    
    #see if model has already been compiled. If not, compile and save it
    import os
    model_file="./XID+highz.pkl"
    try:
       with open(model_file,'rb') as f:
            # using the same model as before
            print("%s found. Reusing" % model_file)
            sm = pickle.load(f)
            fit = sm.sampling(data=XID_data,iter=iter,chains=chains)
    except IOError as e:
        print("%s not found. Compiling" % model_file)
        sm = pystan.StanModel(file=stan_path+'XID+highz.stan')
        # save it to the file 'model.pkl' for later use
        with open(model_file, 'wb') as f:
            pickle.dump(sm, f)
        fit = sm.sampling(data=XID_data,iter=iter,chains=chains)

    #extract fit
    fit_data=fit.extract(permuted=False, inc_warmup=False)
    #return fit data
    return fit_data,chains,iter

def lstdrv_stan(prior,chains=4,iter=1000):
    #
    import pystan
    import pickle

    # define function to initialise flux values to one
    def initfun():
        return dict(src_f=np.ones(snsrc))
    #input data into a dictionary

    XID_data={'npix':prior.snpix,
          'nsrc':prior.nsrc,
          'nnz':prior.amat_data.size,
          'db':prior.sim,
          'sigma':prior.snim,
          'bkg_prior':prior.bkg[0],
          'bkg_prior_sig':prior.bkg[1],
          'Val':prior.amat_data,
          'Row': prior.amat_row.astype(long),
          'Col': prior.amat_col.astype(long)}
    
    #see if model has already been compiled. If not, compile and save it
    import os
    model_file="./XID+_basic.pkl"
    try:
       with open(model_file,'rb') as f:
            # using the same model as before
            print("%s found. Reusing" % model_file)
            sm = pickle.load(f)
            fit = sm.sampling(data=XID_data,iter=iter,chains=chains)
    except IOError as e:
        print("%s not found. Compiling" % model_file)
        sm = pystan.StanModel(file=stan_path+'XIDfit.stan')
        # save it to the file 'model.pkl' for later use
        with open(model_file, 'wb') as f:
            pickle.dump(sm, f)
        fit = sm.sampling(data=XID_data,iter=iter,chains=chains)
    #extract fit
    fit_data=fit.extract(permuted=False, inc_warmup=False)
    #return fit data
    return fit_data,chains,iter

def lstdrv_SPIRE_prior_stan(SPIRE_250,SPIRE_350,SPIRE_500,chains=4,iter=1000):
    """Fit all three SPIRE maps using stan"""
    import pystan
    import pickle

    # define function to initialise flux values to one
    def initfun():
        return dict(src_f=np.ones(snsrc))
    #input data into a dictionary
        
    XID_data={'nsrc':SPIRE_250.nsrc,
          'npix_psw':SPIRE_250.snpix,
          'nnz_psw':SPIRE_250.amat_data.size,
          'db_psw':SPIRE_250.sim,
          'sigma_psw':SPIRE_250.snim,
          'bkg_prior_psw':SPIRE_250.bkg[0],
          'bkg_prior_sig_psw':SPIRE_250.bkg[1],
          'Val_psw':SPIRE_250.amat_data,
          'Row_psw': SPIRE_250.amat_row.astype(long),
          'Col_psw': SPIRE_250.amat_col.astype(long),
          'psw_prior': SPIRE_250.sflux,
          'npix_pmw':SPIRE_350.snpix,
          'nnz_pmw':SPIRE_350.amat_data.size,
          'db_pmw':SPIRE_350.sim,
          'sigma_pmw':SPIRE_350.snim,
          'bkg_prior_pmw':SPIRE_350.bkg[0],
          'bkg_prior_sig_pmw':SPIRE_350.bkg[1],
          'Val_pmw':SPIRE_350.amat_data,
          'Row_pmw': SPIRE_350.amat_row.astype(long),
          'Col_pmw': SPIRE_350.amat_col.astype(long),
          'pmw_prior': SPIRE_350.sflux,
          'npix_plw':SPIRE_500.snpix,
          'nnz_plw':SPIRE_500.amat_data.size,
          'db_plw':SPIRE_500.sim,
          'sigma_plw':SPIRE_500.snim,
          'bkg_prior_plw':SPIRE_500.bkg[0],
          'bkg_prior_sig_plw':SPIRE_500.bkg[1],
          'Val_plw':SPIRE_500.amat_data,
          'Row_plw': SPIRE_500.amat_row.astype(long),
          'Col_plw': SPIRE_500.amat_col.astype(long),
          'plw_prior': SPIRE_500.sflux}
    
    #see if model has already been compiled. If not, compile and save it
    import os
    model_file="./XID+SPIRE_prior.pkl"
    try:
       with open(model_file,'rb') as f:
            # using the same model as before
            print("%s found. Reusing" % model_file)
            sm = pickle.load(f)
            fit = sm.sampling(data=XID_data,iter=iter,chains=chains)
    except IOError as e:
        print("%s not found. Compiling" % model_file)
        sm = pystan.StanModel(file=stan_path+'XID+SPIRE_prior.stan')
        # save it to the file 'model.pkl' for later use
        with open(model_file, 'wb') as f:
            pickle.dump(sm, f)
        fit = sm.sampling(data=XID_data,iter=iter,chains=chains)
    #extract fit
    fit_data=fit.extract(permuted=False, inc_warmup=False)
    #return fit data
    return fit_data,chains,iter

class posterior_stan(object):
    def __init__(self,stan_fit,nsrc):
        """ Class for dealing with posterior from stan"""
        self.stan_fit=stan_fit
        self.nsrc=nsrc
    
    def convergence_stats(self):
        #function to calculate the between and within-sequence variance,
        #marginal posterior variance, and R
        #for one parameter, as described in DAT,sec 11.4
        #(function will split each chain into two)
        #chain is a n,m array, n=number of iterations,m=number of chains
        #chain should not include warmup
        #will return B,W,var_psi_y,R
        R=np.array([])
        n,m,s=self.stan_fit.shape
        for i in range(0,s):
            n_2=n/2.0
            psi_j=np.empty((2*m))
            s2_j=np.empty((2*m))
            for j in range(0,m):
                psi_j[j]=np.mean(self.stan_fit[0:n/2.0,j,i])
                psi_j[j+m]=np.mean(self.stan_fit[n/2.0:,j,i])
                #print np.power(chain[0:n/2.0,j]-psi_j[j],2)
                #print np.power(chain[n/2.0:,j]-psi_j[j+m],2)
                s2_j[j]=(1.0/((n/2.0)-1))*np.sum(np.power(self.stan_fit[0:n/2.0,j,i]-psi_j[j],2))
                s2_j[j+m]=(1.0/((n/2.0)-1))*np.sum(np.power(self.stan_fit[n/2.0:,j,i]-psi_j[j+m],2))

            psi=np.mean(psi_j)
            B=((n/2.0)/(2.0*m-1))*np.sum(np.power(psi_j-psi,2))
            W=np.mean(s2_j)
            var_psi_y=(((n_2-1)/n_2)*W)
            R=np.append(R,np.power(var_psi_y/W,0.5))
        return R
    
    # define a function to get percentile for a particular parameter
    def quantileGet(self,q):
        chains,iter,nparam=self.stan_fit.shape
        param=self.stan_fit.reshape((chains*iter,nparam))
        #q is quantile
        #param is array (nsamples,nparameters)
        # make a list to store the quantiles
        quants = []
 
        # for every predicted value
        for i in range(param.shape[1]):
            # make a vector to store the predictions from each chain
            val = []
 
            # next go down the rows and store the values
            for j in range(param.shape[0]):
                val.append(param[j,i])
 
            # return the quantile for the predictions.
            quants.append(np.percentile(val, q))
 
        return quants
    
    def covariance_sparse(self,threshold=0.1):
        """Create sparse covariance matrix from posterior. \n 
        Only stores values that are greater than given threshold (default=|0.1|)"""
        chains,iter,nparam=self.stan_fit.shape
        #Create index for sources that correspond to index in covariance matrix
        ij=np.append(np.arange(0,self.nsrc+1),[np.arange(0,self.nsrc+1),np.arange(0,self.nsrc+1)])
        #Create index for band that correspond to index in covarariance matrix
        bb=np.append(np.full(self.nsrc+1,0),[np.full(self.nsrc+1,1),np.full(self.nsrc+1,2)])
        i_cov,j_cov=np.meshgrid(ij,ij)
        k_cov,l_cov=np.meshgrid(bb,bb)
        #Calculate covariance matrix
        cov=np.cov(self.stan_fit.reshape((chains*iter,nparam)).T)
        #Rather than storing full cov matrix, use only upper triangle (and diag)
        cov=np.triu(cov,0) #this sets lower tri to zero
        #select elements greater than threshold
        index=np.abs(cov)>threshold
        self.XID_i=i_cov[index]
        self.XID_j=j_cov[index]
        self.Band_k=k_cov[index]
        self.Band_l=l_cov[index]
        self.sigma_i_j_k_l=cov[index]

def create_XIDp_cat(posterior,prior):
    """creates the XIDp catalogue for one band, in fits format required by HeDaM"""
    import datetime
    nsrc=posterior.nsrc
    med_flux=posterior.quantileGet(50)
    flux_low=posterior.quantileGet(15.87)
    flux_high=posterior.quantileGet(84.1)
    #----table info-----------------------
    #first define columns
    c1 = fits.Column(name='XID', format='I', array=np.arange(posterior.nsrc,dtype=long))
    c2 = fits.Column(name='ra', format='D', unit='degrees', array=prior.sra)
    c3 = fits.Column(name='dec', format='D', unit='degrees', array=prior.sdec)
    c4 = fits.Column(name='flux', format='E', unit='mJy', array=med_flux[0:nsrc])
    c5 = fits.Column(name='flux_err_u', format='E', unit='mJy', array=flux_high[0:nsrc])
    c6 = fits.Column(name='flux_err_l', format='E', unit='mJy', array=flux_low[0:nsrc])
    c7 = fits.Column(name='bkg', format='E', unit='mJy', array=np.full(nsrc,med_flux[nsrc]))
    tbhdu = fits.new_table([c1,c2,c3,c4,c5,c6,c7])
    
    tbhdu.header.set('TUCD1','XID',after='TFORM1')      
    tbhdu.header.set('TDESC1','ID of source which corresponds to i and j of cov matrix.',after='TUCD1')         

    tbhdu.header.set('TUCD2','pos.eq.RA',after='TUNIT2')      
    tbhdu.header.set('TDESC2','R.A. of object J2000',after='TUCD2') 

    tbhdu.header.set('TUCD3','pos.eq.DEC',after='TUNIT3')      
    tbhdu.header.set('TDESC3','Dec. of object J2000',after='TUCD3') 

    tbhdu.header.set('TUCD4','phot.flux.density',after='TUNIT4')      
    tbhdu.header.set('TDESC4','Flux (at 50th percentile)',after='TUCD4') 

    tbhdu.header.set('TUCD5','phot.flux.density',after='TUNIT5')      
    tbhdu.header.set('TDESC5','Flux (at 84.1 percentile) ',after='TUCD5') 

    tbhdu.header.set('TUCD6','phot.flux.density',after='TUNIT6')      
    tbhdu.header.set('TDESC6','Flux (at 15.87 percentile)',after='TUCD6') 

    tbhdu.header.set('TUCD7','phot.flux.density',after='TUNIT7')      
    tbhdu.header.set('TDESC7','background',after='TUCD7') 
 
    #----Primary header-----------------------------------
    prihdr = fits.Header()
    prihdr['Prior_C'] = prior.prior_cat
    prihdr['TITLE']   = 'SPIRE XID catalogue'        
    #prihdr['OBJECT']  = prior.imphdu['OBJECT']                              
    prihdr['CREATOR'] = 'WP5'                                 
    prihdr['VERSION'] = 'beta'                                 
    prihdr['DATE']    = datetime.datetime.now().isoformat()              
    prihdu = fits.PrimaryHDU(header=prihdr)
    
    thdulist = fits.HDUList([prihdu, tbhdu,fits.ImageHDU(header=prior.imphdu)])
    return thdulist


def create_XIDp_SPIREcat(posterior,prior250,prior350,prior500):
    """creates the XIDp catalogue in fits format required by HeDaM"""
    import datetime
    nsrc=posterior.nsrc
    med_flux=posterior.quantileGet(50)
    flux_low=posterior.quantileGet(15.87)
    flux_high=posterior.quantileGet(84.1)



    #----table info-----------------------
    #first define columns
    c1 = fits.Column(name='XID', format='I', array=np.arange(posterior.nsrc,dtype=long))
    c2 = fits.Column(name='ra', format='D', unit='degrees', array=prior250.sra)
    c3 = fits.Column(name='dec', format='D', unit='degrees', array=prior250.sdec)
    c4 = fits.Column(name='flux250', format='E', unit='mJy', array=med_flux[0:nsrc])
    c5 = fits.Column(name='flux250_err_u', format='E', unit='mJy', array=flux_high[0:nsrc])
    c6 = fits.Column(name='flux250_err_l', format='E', unit='mJy', array=flux_low[0:nsrc])
    c7 = fits.Column(name='flux350', format='E', unit='mJy', array=med_flux[nsrc+1:(2*nsrc)+1])
    c8 = fits.Column(name='flux350_err_u', format='E', unit='mJy', array=flux_high[nsrc+1:(2*nsrc)+1])
    c9 = fits.Column(name='flux350_err_l', format='E', unit='mJy', array=flux_low[nsrc+1:(2*nsrc)+1])
    c10 = fits.Column(name='flux500', format='E', unit='mJy', array=med_flux[2*nsrc+2:(3*nsrc)+2])
    c11 = fits.Column(name='flux500_err_u', format='E', unit='mJy', array=flux_high[2*nsrc+2:(3*nsrc)+2])
    c12 = fits.Column(name='flux500_err_l', format='E', unit='mJy', array=flux_low[2*nsrc+2:(3*nsrc)+2])
    c13 = fits.Column(name='bkg250', format='E', unit='mJy', array=np.full(nsrc,med_flux[nsrc]))
    c14 = fits.Column(name='bkg350', format='E', unit='mJy', array=np.full(nsrc,med_flux[(2*nsrc)+1]))
    c15 = fits.Column(name='bkg500', format='E', unit='mJy', array=np.full(nsrc,med_flux[(3*nsrc)+2]))

    tbhdu = fits.new_table([c1,c2,c3,c4,c5,c6,c7,c8,c9,c10,c11,c12,c13,c14,c15])
    
    tbhdu.header.set('TUCD1','XID',after='TFORM1')      
    tbhdu.header.set('TDESC1','ID of source which corresponds to i and j of cov matrix.',after='TUCD1')         

    tbhdu.header.set('TUCD2','pos.eq.RA',after='TUNIT2')      
    tbhdu.header.set('TDESC2','R.A. of object J2000',after='TUCD2') 

    tbhdu.header.set('TUCD3','pos.eq.DEC',after='TUNIT3')      
    tbhdu.header.set('TDESC3','Dec. of object J2000',after='TUCD3') 

    tbhdu.header.set('TUCD4','phot.flux.density',after='TUNIT4')      
    tbhdu.header.set('TDESC4','250 Flux (at 50th percentile)',after='TUCD4') 

    tbhdu.header.set('TUCD5','phot.flux.density',after='TUNIT5')      
    tbhdu.header.set('TDESC5','250 Flux (at 84.1 percentile) ',after='TUCD5') 

    tbhdu.header.set('TUCD6','phot.flux.density',after='TUNIT6')      
    tbhdu.header.set('TDESC6','250 Flux (at 25.9 percentile)',after='TUCD6') 

    tbhdu.header.set('TUCD7','phot.flux.density',after='TUNIT7')      
    tbhdu.header.set('TDESC7','350 Flux (at 50th percentile)',after='TUCD7') 

    tbhdu.header.set('TUCD8','phot.flux.density',after='TUNIT8')      
    tbhdu.header.set('TDESC8','350 Flux (at 84.1 percentile) ',after='TUCD8') 

    tbhdu.header.set('TUCD9','phot.flux.density',after='TUNIT9')      
    tbhdu.header.set('TDESC9','350 Flux (at 25.9 percentile)',after='TUCD9') 

    tbhdu.header.set('TUCD10','phot.flux.density',after='TUNIT10')      
    tbhdu.header.set('TDESC10','500 Flux (at 50th percentile)',after='TUCD10') 

    tbhdu.header.set('TUCD11','phot.flux.density',after='TUNIT11')      
    tbhdu.header.set('TDESC11','500 Flux (at 84.1 percentile) ',after='TUCD11') 

    tbhdu.header.set('TUCD12','phot.flux.density',after='TUNIT12')      
    tbhdu.header.set('TDESC12','500 Flux (at 25.9 percentile)',after='TUCD12')

    tbhdu.header.set('TUCD13','phot.flux.density',after='TUNIT13')      
    tbhdu.header.set('TDESC13','250 background',after='TUCD13') 

    tbhdu.header.set('TUCD14','phot.flux.density',after='TUNIT14')      
    tbhdu.header.set('TDESC14','350 background',after='TUCD14') 

    tbhdu.header.set('TUCD15','phot.flux.density',after='TUNIT15')      
    tbhdu.header.set('TDESC15','500 background',after='TUCD15')
    
    #----Primary header-----------------------------------
    prihdr = fits.Header()
    prihdr['Prior_C'] = prior250.prior_cat
    prihdr['TITLE']   = 'SPIRE XID catalogue'        
    #prihdr['OBJECT']  = prior250.imphdu['OBJECT'] #I need to think if this needs to change                              
    prihdr['CREATOR'] = 'WP5'                                 
    prihdr['VERSION'] = 'beta'                                 
    prihdr['DATE']    = datetime.datetime.now().isoformat()              
    prihdu = fits.PrimaryHDU(header=prihdr)
    
    #-----Covariance header---------------------------------
    #calcualte the sparse covariance matrix for the posterior
    posterior.covariance_sparse()
    
    c1 = fits.Column(name='sigma_i_j_k_l', format='E', array=posterior.sigma_i_j_k_l)
    c2 = fits.Column(name='XID_i', format='I', array=posterior.XID_i)
    c3 = fits.Column(name='XID_j', format='I', array=posterior.XID_j)
    c4 = fits.Column(name='Band_k', format='I', array=posterior.Band_k)
    c5 = fits.Column(name='Band_l', format='I', array=posterior.Band_l)

    covhdu = fits.new_table([c1,c2,c3,c4,c5])
    covhdu.header.set('TUCD1','covariance',after='TFORM1')      
    covhdu.header.set('TDESC1','covariance between source i and j observed in bands k and l',after='TUCD1')         

    covhdu.header.set('TUCD2','ID',after='TFORM2')      
    covhdu.header.set('TDESC2','XID index of source i',after='TUCD2') 

    covhdu.header.set('TUCD3','ID',after='TFORM3')      
    covhdu.header.set('TDESC3','XID index of source j',after='TUCD3') 

    covhdu.header.set('TUCD4','ID',after='TFORM4')      
    covhdu.header.set('TDESC4','Band source i is observed in',after='TUCD4') 

    covhdu.header.set('TUCD5','ID',after='TFORM5')      
    covhdu.header.set('TDESC5','Band source j is observed in',after='TUCD5') 

    thdulist = fits.HDUList([prihdu, tbhdu, covhdu,fits.ImageHDU(header=prior250.imphdu), fits.ImageHDU(header=prior350.imphdu), fits.ImageHDU(header=prior500.imphdu)])
    return thdulist

def fit_SPIRE(prior250,prior350,prior500):
    prior250.get_pointing_matrix()
    prior350.get_pointing_matrix()
    prior500.get_pointing_matrix()
    fit_data,chains,iter=lstdrv_SPIRE_stan(prior250,prior350,prior500)
    
    posterior=posterior_stan(fit_data[:,:,0:-1],prior250.nsrc)
    return create_XIDp_SPIREcat(posterior,prior250,prior350,prior500),prior250,prior350,prior500,posterior

def SPIRE_PSF(file,pixsize):
    """ Takes in file for PSF and return arrays for get_pointing_matrix. \n Assumes beam is from ftp://ftp.sciops.esa.int/pub/hsc-calibration/SPIRE/PHOT/Beams-1arcsec-shadow/ """
    hdulist = fits.open(file) #Read in file
    PSF=hdulist[1].data
    hdulist.close()
    offset=50 #How many pixels each side of centre do we want in array
    centre=((PSF.shape[0]-1)/2.0) #get centre
    PSF_cut=PSF[centre-offset:centre+offset+1,centre-offset:centre+offset+1] #Cut array to required size
    px,py=PSF_cut.shape
    pindx=np.arange(0,px,1)*1.0/pixsize #get x scale in terms of pixel scale of map
    pindy=np.arange(0,py,1)*1.0/pixsize #get y scale in terms of pixel scale of map
    return PSF_cut,pindx,pindy


def Segmentation_scheme(inra,indec,tile_l):
    """For a given prior catalogue, create a tiling scheme with given tile size. \n Returns tiles for which there are sources""" 
    ra_min=np.floor(10.0*np.min(inra))/10.0
    ra_max=np.floor(10.0*np.max(inra))/10.0
    dec_min=np.floor(10.0*np.min(indec))/10.0
    dec_max=np.floor(10.0*np.max(indec))/10.0

    #Create array to store optimum tile for each source
    tiling_list=np.empty((inra.size,5))
    #Create tiles
    tiles=[]
    tiling_list[:,4]=tile_l
    for ra in np.arange(ra_min,ra_max,0.75*tile_l):
        for dec in np.arange(dec_min,dec_max,0.75*tile_l):
            #create tile for this ra and dec
            tile=np.array([[ra,dec],[ra+tile_l,dec],[ra+tile_l,dec+tile_l],[ra,dec+tile_l]]).T
            #check how many sources are in this tile
            sgood=(inra > tile[0,0]) & (inra < tile[0,1]) & (indec > tile[1,0]) & (indec < tile[1,2])

            if sgood.sum() >0:
                tiles.append(tile)
                #work out distance from tile centre to each source in tile
                dist=np.power(np.power((ra+tile_l/2.0)-inra[sgood],2)+np.power((dec+tile_l/2.0)-indec[sgood],2),0.5)
                ii=0
                for i in np.arange(0,inra.size)[sgood]:
                    #store ra and dec of optimum tile as well as distance
                    if tiling_list[i,4] > dist[ii]:
                        tiling_list[i,:]=[inra[i],indec[i],ra,dec,dist[ii]]
                    ii+=1
    return tiles, tiling_list
    
def create_empty_XIDp_SPIREcat(nsrc):
    """creates the XIDp catalogue in fits format required by HeDaM"""
    import datetime



    #----table info-----------------------
    #first define columns
    c1 = fits.Column(name='XID', format='I', array=np.empty((nsrc), dtype=long))
    c2 = fits.Column(name='ra', format='D', unit='degrees', array=np.empty((nsrc)))
    c3 = fits.Column(name='dec', format='D', unit='degrees', array=np.empty((nsrc)))
    c4 = fits.Column(name='flux250', format='E', unit='mJy', array=np.empty((nsrc)))
    c5 = fits.Column(name='flux250_err_u', format='E', unit='mJy', array=np.empty((nsrc)))
    c6 = fits.Column(name='flux250_err_l', format='E', unit='mJy', array=np.empty((nsrc)))
    c7 = fits.Column(name='flux350', format='E', unit='mJy', array=np.empty((nsrc)))
    c8 = fits.Column(name='flux350_err_u', format='E', unit='mJy', array=np.empty((nsrc)))
    c9 = fits.Column(name='flux350_err_l', format='E', unit='mJy', array=np.empty((nsrc)))
    c10 = fits.Column(name='flux500', format='E', unit='mJy', array=np.empty((nsrc)))
    c11 = fits.Column(name='flux500_err_u', format='E', unit='mJy', array=np.empty((nsrc)))
    c12 = fits.Column(name='flux500_err_l', format='E', unit='mJy', array=np.empty((nsrc)))
    c13 = fits.Column(name='bkg250', format='E', unit='mJy', array=np.empty((nsrc)))
    c14 = fits.Column(name='bkg350', format='E', unit='mJy', array=np.empty((nsrc)))
    c15 = fits.Column(name='bkg500', format='E', unit='mJy', array=np.empty((nsrc)))

    tbhdu = fits.new_table([c1,c2,c3,c4,c5,c6,c7,c8,c9,c10,c11,c12,c13,c14,c15])
    
    tbhdu.header.set('TUCD1','XID',after='TFORM1')      
    tbhdu.header.set('TDESC1','ID of source which corresponds to i and j of cov matrix.',after='TUCD1')         

    tbhdu.header.set('TUCD2','pos.eq.RA',after='TUNIT2')      
    tbhdu.header.set('TDESC2','R.A. of object J2000',after='TUCD2') 

    tbhdu.header.set('TUCD3','pos.eq.DEC',after='TUNIT3')      
    tbhdu.header.set('TDESC3','Dec. of object J2000',after='TUCD3') 

    tbhdu.header.set('TUCD4','phot.flux.density',after='TUNIT4')      
    tbhdu.header.set('TDESC4','250 Flux (at 50th percentile)',after='TUCD4') 

    tbhdu.header.set('TUCD5','phot.flux.density',after='TUNIT5')      
    tbhdu.header.set('TDESC5','250 Flux (at 84.1 percentile) ',after='TUCD5') 

    tbhdu.header.set('TUCD6','phot.flux.density',after='TUNIT6')      
    tbhdu.header.set('TDESC6','250 Flux (at 25.9 percentile)',after='TUCD6') 

    tbhdu.header.set('TUCD7','phot.flux.density',after='TUNIT7')      
    tbhdu.header.set('TDESC7','350 Flux (at 50th percentile)',after='TUCD7') 

    tbhdu.header.set('TUCD8','phot.flux.density',after='TUNIT8')      
    tbhdu.header.set('TDESC8','350 Flux (at 84.1 percentile) ',after='TUCD8') 

    tbhdu.header.set('TUCD9','phot.flux.density',after='TUNIT9')      
    tbhdu.header.set('TDESC9','350 Flux (at 25.9 percentile)',after='TUCD9') 

    tbhdu.header.set('TUCD10','phot.flux.density',after='TUNIT10')      
    tbhdu.header.set('TDESC10','500 Flux (at 50th percentile)',after='TUCD10') 

    tbhdu.header.set('TUCD11','phot.flux.density',after='TUNIT11')      
    tbhdu.header.set('TDESC11','500 Flux (at 84.1 percentile) ',after='TUCD11') 

    tbhdu.header.set('TUCD12','phot.flux.density',after='TUNIT12')      
    tbhdu.header.set('TDESC12','500 Flux (at 25.9 percentile)',after='TUCD12')

    tbhdu.header.set('TUCD13','phot.flux.density',after='TUNIT13')      
    tbhdu.header.set('TDESC13','250 background',after='TUCD13') 

    tbhdu.header.set('TUCD14','phot.flux.density',after='TUNIT14')      
    tbhdu.header.set('TDESC14','350 background',after='TUCD14') 

    tbhdu.header.set('TUCD15','phot.flux.density',after='TUNIT15')      
    tbhdu.header.set('TDESC15','500 background',after='TUCD15')
    
    #----Primary header-----------------------------------
    prihdr = fits.Header()
    #prihdr['Prior_C'] = prior250.prior_cat
    prihdr['TITLE']   = 'SPIRE XID catalogue'        
    #prihdr['OBJECT']  = prior250.imphdu['OBJECT'] #I need to think if this needs to change                              
    prihdr['CREATOR'] = 'WP5'                                 
    prihdr['VERSION'] = 'beta'                                 
    prihdr['DATE']    = datetime.datetime.now().isoformat()              
    prihdu = fits.PrimaryHDU(header=prihdr)
    
    thdulist = fits.HDUList([prihdu, tbhdu])
    return thdulist

def create_XIDp_SPIREcat_nocov(posterior,prior250,prior350,prior500):
    """creates the XIDp catalogue in fits format required by HeDaM"""
    import datetime
    nsrc=posterior.nsrc
    med_flux=posterior.quantileGet(50)
    flux_low=posterior.quantileGet(15.87)
    flux_high=posterior.quantileGet(84.1)



    #----table info-----------------------
    #first define columns
    c1 = fits.Column(name='XID', format='I', array=np.arange(posterior.nsrc,dtype=long))
    c2 = fits.Column(name='ra', format='D', unit='degrees', array=prior250.sra)
    c3 = fits.Column(name='dec', format='D', unit='degrees', array=prior250.sdec)
    c4 = fits.Column(name='flux250', format='E', unit='mJy', array=med_flux[0:nsrc])
    c5 = fits.Column(name='flux250_err_u', format='E', unit='mJy', array=flux_high[0:nsrc])
    c6 = fits.Column(name='flux250_err_l', format='E', unit='mJy', array=flux_low[0:nsrc])
    c7 = fits.Column(name='flux350', format='E', unit='mJy', array=med_flux[nsrc+1:(2*nsrc)+1])
    c8 = fits.Column(name='flux350_err_u', format='E', unit='mJy', array=flux_high[nsrc+1:(2*nsrc)+1])
    c9 = fits.Column(name='flux350_err_l', format='E', unit='mJy', array=flux_low[nsrc+1:(2*nsrc)+1])
    c10 = fits.Column(name='flux500', format='E', unit='mJy', array=med_flux[2*nsrc+2:(3*nsrc)+2])
    c11 = fits.Column(name='flux500_err_u', format='E', unit='mJy', array=flux_high[2*nsrc+2:(3*nsrc)+2])
    c12 = fits.Column(name='flux500_err_l', format='E', unit='mJy', array=flux_low[2*nsrc+2:(3*nsrc)+2])
    c13 = fits.Column(name='bkg250', format='E', unit='mJy', array=np.full(nsrc,med_flux[nsrc]))
    c14 = fits.Column(name='bkg350', format='E', unit='mJy', array=np.full(nsrc,med_flux[(2*nsrc)+1]))
    c15 = fits.Column(name='bkg500', format='E', unit='mJy', array=np.full(nsrc,med_flux[(3*nsrc)+2]))

    tbhdu = fits.new_table([c1,c2,c3,c4,c5,c6,c7,c8,c9,c10,c11,c12,c13,c14,c15])
    
    tbhdu.header.set('TUCD1','XID',after='TFORM1')      
    tbhdu.header.set('TDESC1','ID of source which corresponds to i and j of cov matrix.',after='TUCD1')         

    tbhdu.header.set('TUCD2','pos.eq.RA',after='TUNIT2')      
    tbhdu.header.set('TDESC2','R.A. of object J2000',after='TUCD2') 

    tbhdu.header.set('TUCD3','pos.eq.DEC',after='TUNIT3')      
    tbhdu.header.set('TDESC3','Dec. of object J2000',after='TUCD3') 

    tbhdu.header.set('TUCD4','phot.flux.density',after='TUNIT4')      
    tbhdu.header.set('TDESC4','250 Flux (at 50th percentile)',after='TUCD4') 

    tbhdu.header.set('TUCD5','phot.flux.density',after='TUNIT5')      
    tbhdu.header.set('TDESC5','250 Flux (at 84.1 percentile) ',after='TUCD5') 

    tbhdu.header.set('TUCD6','phot.flux.density',after='TUNIT6')      
    tbhdu.header.set('TDESC6','250 Flux (at 25.9 percentile)',after='TUCD6') 

    tbhdu.header.set('TUCD7','phot.flux.density',after='TUNIT7')      
    tbhdu.header.set('TDESC7','350 Flux (at 50th percentile)',after='TUCD7') 

    tbhdu.header.set('TUCD8','phot.flux.density',after='TUNIT8')      
    tbhdu.header.set('TDESC8','350 Flux (at 84.1 percentile) ',after='TUCD8') 

    tbhdu.header.set('TUCD9','phot.flux.density',after='TUNIT9')      
    tbhdu.header.set('TDESC9','350 Flux (at 25.9 percentile)',after='TUCD9') 

    tbhdu.header.set('TUCD10','phot.flux.density',after='TUNIT10')      
    tbhdu.header.set('TDESC10','500 Flux (at 50th percentile)',after='TUCD10') 

    tbhdu.header.set('TUCD11','phot.flux.density',after='TUNIT11')      
    tbhdu.header.set('TDESC11','500 Flux (at 84.1 percentile) ',after='TUCD11') 

    tbhdu.header.set('TUCD12','phot.flux.density',after='TUNIT12')      
    tbhdu.header.set('TDESC12','500 Flux (at 25.9 percentile)',after='TUCD12')

    tbhdu.header.set('TUCD13','phot.flux.density',after='TUNIT13')      
    tbhdu.header.set('TDESC13','250 background',after='TUCD13') 

    tbhdu.header.set('TUCD14','phot.flux.density',after='TUNIT14')      
    tbhdu.header.set('TDESC14','350 background',after='TUCD14') 

    tbhdu.header.set('TUCD15','phot.flux.density',after='TUNIT15')      
    tbhdu.header.set('TDESC15','500 background',after='TUCD15')
    
    #----Primary header-----------------------------------
    prihdr = fits.Header()
    prihdr['Prior_C'] = prior250.prior_cat
    prihdr['TITLE']   = 'SPIRE XID catalogue'        
    #prihdr['OBJECT']  = prior250.imphdu['OBJECT'] #I need to think if this needs to change                              
    prihdr['CREATOR'] = 'WP5'                                 
    prihdr['VERSION'] = 'beta'                                 
    prihdr['DATE']    = datetime.datetime.now().isoformat()              
    prihdu = fits.PrimaryHDU(header=prihdr)
    
    thdulist = fits.HDUList([prihdu, tbhdu,fits.ImageHDU(header=prior250.imphdu), fits.ImageHDU(header=prior350.imphdu), fits.ImageHDU(header=prior500.imphdu)])
    return thdulist
