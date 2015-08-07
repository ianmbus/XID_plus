from astropy.io import fits
import numpy as np
import matplotlib
import pylab as plt
import scipy.stats as stats
from scipy.stats import norm



def metrics_XIDp(samples,truth):
    """ returns error percent, precision (IQR/median), and accuracy ((output-truth)/truth) from XIDp samples (no.samp,no. parameters)"""
    nsamp,nparam = samples.shape
    error_percent=np.empty((nparam))
    IQR_med=np.empty((nparam))
    accuracy=np.empty((nparam))
    for i in range(0,nparam):
        error_percent[i]=norm.ppf(stats.percentileofscore(samples[:,i],truth[i])/100.0,loc=0,scale=1)
        IQR_med[i]=np.subtract(*np.percentile(samples[:,i],[75.0,25.0]))#/np.median(samples[:,i])
        accuracy[i]=(np.median(samples[:,i])-truth[i])#/truth[i]
    return error_percent,IQR_med,accuracy


def metrics_plot(metric,truth,bins,labels,ylim,yscale='linear'):
    def upper(x):
        return np.percentile(x,[84.1])
    def lower(x):
        return np.percentile(x,[15.9])
        
    fig,ax=plt.subplots(figsize=(5.5,5))
    ind_good=np.isfinite(metric)
    mean=stats.binned_statistic(truth[ind_good],metric[ind_good],statistic='mean',bins=bins)
    std_dev=stats.binned_statistic(truth[ind_good],metric[ind_good],statistic=np.std,bins=bins)
    sig_plus=stats.binned_statistic(truth[ind_good],metric[ind_good],statistic=upper,bins=bins)
    sig_neg=stats.binned_statistic(truth[ind_good],metric[ind_good],statistic=lower,bins=bins)

    blues=plt.get_cmap('Blues')

    ax.plot(bins[1:],mean[0],'r')
    ax.plot(bins[1:],sig_plus[0],'r--')
    ax.plot(bins[1:],sig_neg[0],'r--')
    #ax.plot(bins[0:-1],mean[0]-std_dev[0],'r--')
    #ax.plot(bins[0:-1],mean[0]+std_dev[0],'r--')
    ax.set_xlabel(labels[0])
    ax.set_xscale('log')
    ax.set_ylabel(labels[1])
    ax.set_xlim((np.min(bins),np.max(bins)))
    ind_good_hex=(metric > np.min(mean[0])-2*np.max(std_dev[0])) & (metric < np.max(mean[0])+2*np.max(std_dev[0]))
    if yscale !='linear':
        ax.set_yscale('log')
        tmp = ax.hexbin(truth[ind_good_hex], metric[ind_good_hex], gridsize=40, cmap=blues,xscale = 'log',yscale='log')#,extent=(np.min(truth),np.max(truth),np.min(mean[0])-2*np.max(std_dev[0]),np.max(mean[0])+2*np.max(std_dev[0])))
    else:
        tmp = ax.hexbin(truth[ind_good_hex], metric[ind_good_hex], gridsize=40, cmap=blues,xscale = 'log')#,extent=(np.min(truth),np.max(truth),np.min(mean[0])-2*np.max(std_dev[0]),np.max(mean[0])+2*np.max(std_dev[0])))

    ax.set_ylim(ylim)

    fig.colorbar(tmp, ax=ax)
    return fig