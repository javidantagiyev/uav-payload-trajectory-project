"""stage 6: measured-tower QA, matched-information evaluation, blocked checks, figures."""
from __future__ import annotations

from pathlib import Path
import argparse
import json
import math
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import pandas as pd

from src.physics.atmospheric_observations import load_profiles, sha256_file
from src.physics.atmospheric_stage6 import (
    make_observation_table, build_targets, all_model_predictions,
    direction_errors, metrics, grouped_metrics, paired_day_bootstrap,
    temporal_holdout, quality_report, reference_speed_bins,
    PRIMARY_MODELS, EXTRA_MODELS,
)

DEFAULT_CSV=ROOT/'results/atmospheric_testbed/6g_stage5/verified/cabauw_observations_enu.csv'
DEFAULT_META=ROOT/'results/atmospheric_testbed/6g_stage5/verified/cabauw_observations.metadata.json'
DEFAULT_OUT=ROOT/'results/atmospheric_testbed/6g_stage6'


def _save(fig, folder, name):
    fig.tight_layout()
    fig.savefig(folder/name,dpi=175,bbox_inches='tight')
    plt.close(fig)
    return name


def _fmt_dates(ax):
    ax.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=3,maxticks=8))
    ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(ax.xaxis.get_major_locator()))


def make_figures(obs, pred, day_metrics, height_metrics, fold, output):
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    made=[]
    selected=["no_shear_10m","power_1_7_fixed","neutral_log_z0_003_fixed",
              "power_alpha_heldout_day","log_z0_heldout_day"]

    # temporal wind profiles at distinct heights
    fig,axes=plt.subplots(2,1,figsize=(12,7),sharex=True)
    for z in (10.,20.,40.,80.,140.,200.):
        sub=obs[obs.height_agl_m==z]
        axes[0].plot(sub.timestamp_utc,sub.speed,label=f'{z:g} m',lw=1.1,alpha=.85)
    axes[0].set(ylabel='Observed wind speed (m/s)',title='Cabauw observed wind: actual UTC timestamps')
    axes[0].legend(ncol=6,fontsize=8);axes[0].grid(alpha=.2)
    for z in (10.,40.,200.):
        sub=obs[obs.height_agl_m==z]
        axes[1].plot(sub.timestamp_utc,sub.east,label=f'east {z:g} m',lw=.9,alpha=.8)
    axes[1].set(xlabel='UTC',ylabel='Observed east wind (m/s)');axes[1].legend(ncol=3,fontsize=8);axes[1].grid(alpha=.2)
    _fmt_dates(axes[1]);made.append(_save(fig,output,'01_observed_wind_by_time.png'))

    # observed multilevel profile at 4 timestamps across observation span
    fig,ax=plt.subplots(figsize=(8,6))
    stamps=sorted(obs.timestamp_utc.unique())
    indices=np.linspace(0,len(stamps)-1,min(5,len(stamps)),dtype=int)
    for i in indices:
        sub=obs[obs.timestamp_utc==stamps[i]].sort_values('height_agl_m')
        ax.plot(sub.speed,sub.height_agl_m,'o-',label=str(stamps[i])[:16])
    ax.set(xlabel='Observed wind speed (m/s)',ylabel='Height AGL (m)',title='Selected observed tower profiles')
    ax.legend(fontsize=8);ax.grid(alpha=.2)
    made.append(_save(fig,output,'02_observed_vertical_profiles.png'))

    # per-height matched-info error
    fig,ax=plt.subplots(figsize=(9,5))
    main=height_metrics[height_metrics.model.isin(selected)]
    for model in selected:
        sub=main[main.model==model].sort_values('height_agl_m')
        ax.plot(sub.height_agl_m,sub.rmse_m_s,'o-',label=model)
    ax.set(xlabel='Held-out height AGL (m)',ylabel='Vector RMSE (m/s)',title='Equal-input comparison: only 10 m wind is observed at test time')
    ax.legend(fontsize=8);ax.grid(alpha=.2)
    made.append(_save(fig,output,'03_matched_input_rmse_by_height.png'))

    # day-by-day RMSE (not 1 long index plot)
    fig,ax=plt.subplots(figsize=(11,5))
    for model in selected:
        sub=day_metrics[day_metrics.model==model].sort_values('date_utc')
        ax.plot(pd.to_datetime(sub.date_utc),sub.rmse_m_s,marker='o',label=model)
    ax.set(xlabel='UTC date',ylabel='Vector RMSE (m/s)',title='Day-by-day held-out-height model error')
    ax.legend(fontsize=8);ax.grid(alpha=.2);_fmt_dates(ax)
    made.append(_save(fig,output,'04_daily_rmse.png'))

    # time series of signed residuals at two heights
    fig,axes=plt.subplots(2,1,figsize=(12,8),sharex=True)
    for i,z in enumerate((20.,40.)):
        ax=axes[i]
        for model in ('no_shear_10m','power_1_7_fixed','power_alpha_heldout_day'):
            sub=pred[(pred.model==model)&(pred.height_agl_m==z)].sort_values('timestamp_utc')
            ax.plot(sub.timestamp_utc,sub.speed_error,lw=.85,alpha=.8,label=model)
        ax.axhline(0,color='gray',lw=.8)
        ax.set(ylabel=f'{z:g} m speed residual (m/s)',title=f'Signed wind-speed error at {z:g} m (UTC)')
        ax.grid(alpha=.2);ax.legend(fontsize=8,ncol=3)
    axes[-1].set_xlabel('UTC');_fmt_dates(axes[-1])
    made.append(_save(fig,output,'05_speed_residuals_actual_time.png'))

    # calibration variability across left-out days
    fig,axes=plt.subplots(2,1,figsize=(10,7),sharex=True)
    dates=pd.to_datetime(fold.date_utc)
    axes[0].plot(dates,fold.power_alpha,'o-');axes[0].set(ylabel='Training-fitted exponent α',title='Model parameters fitted without the held-out UTC day');axes[0].grid(alpha=.2)
    axes[1].plot(dates,fold.log_roughness_m,'o-');axes[1].set(ylabel='Fitted log-law z₀ (m)',xlabel='Held-out UTC day');axes[1].set_yscale('log');axes[1].grid(alpha=.2)
    _fmt_dates(axes[1]);made.append(_save(fig,output,'06_block_cv_parameters.png'))

    # overall vector error CDF, including extra sensor baseline but clearly separated
    fig,ax=plt.subplots(figsize=(10,5))
    for model in ('power_1_7_fixed','power_alpha_heldout_day', 'neutral_log_z0_003_fixed',
                  'interpolation_extra_sensors'):
        data=np.sort(pred[pred.model==model].vector_error.to_numpy())
        ax.plot(data,np.arange(1,len(data)+1)/len(data),label=model)
    ax.set(xlabel='Wind vector error magnitude (m/s)',ylabel='Empirical cumulative fraction',
           title='Error distributions (extra-sensor baseline is not an equal-information comparison)')
    ax.legend(fontsize=8);ax.grid(alpha=.2)
    made.append(_save(fig,output,'07_error_cdf.png'))

    # stratify angular error by reference speed; mask low wind
    sub=pred[(pred.model=='power_1_7_fixed')&(pred.direction_evaluable)]
    fig,axes=plt.subplots(1,2,figsize=(12,5))
    for z in (20.,40.):
        d=sub[sub.height_agl_m==z]
        axes[0].scatter(d.ref_speed,np.abs(d.direction_error_deg),s=6,alpha=.3,label=f'{z:g} m')
    axes[0].set(xlabel='Reference wind speed at 10 m (m/s)',ylabel='Absolute direction error (degrees)',
                title='Direction errors only when all speeds ≥ threshold')
    axes[0].legend();axes[0].grid(alpha=.2)
    ref=obs[obs.height_agl_m==10.]
    axes[1].hist(ref.speed,bins=30)
    axes[1].set(xlabel='10 m observed wind speed (m/s)',ylabel='Number of timestamps',
                title='Reference-wind distribution; calm events affect direction')
    axes[1].grid(alpha=.2)
    made.append(_save(fig,output,'08_direction_and_calm.png'))

    # error vs speed bins incl model comparison
    bins=reference_speed_bins(pred)
    fig,ax=plt.subplots(figsize=(10,5))
    positions=np.arange(3,dtype=float)
    width=.16
    for i,model in enumerate(selected):
        s=bins[bins.model==model]
        v=[]
        for b in ('below_2','2_to_4','4_plus'):
            block=s[s.ref_speed_bin==b]
            v.append(math.sqrt(float(np.mean(block.vector_error**2))) if len(block) else np.nan)
        ax.bar(positions+(i-2)*width,v,width,label=model)
    ax.set_xticks(positions,labels=['<2 m/s','2–4 m/s','≥4 m/s'])
    ax.set(xlabel='Same-time 10 m wind speed',ylabel='Vector RMSE (m/s)',title='Model behavior across reference wind regimes')
    ax.legend(fontsize=8);ax.grid(axis='y',alpha=.2)
    made.append(_save(fig,output,'09_rmse_by_wind_regime.png'))

    # missingness and coverage timeline per sensor
    pivot=obs.assign(valid=1.).pivot(index='timestamp_utc',columns='height_agl_m',values='valid')
    fig,ax=plt.subplots(figsize=(11,3))
    ax.imshow(pivot.T.notna().to_numpy(),aspect='auto',interpolation='nearest',origin='lower',vmin=0,vmax=1,cmap='Greys')
    ax.set_yticks(range(len(pivot.columns)),labels=[f'{z:g} m' for z in pivot.columns])
    ax.set(xlabel='Chronological observation index (10-minute nominal cadence)',title='Measurement presence by height (white = missing)')
    made.append(_save(fig,output,'10_observation_completeness.png'))
    return made


def run(csv_path, metadata_path, out_dir, stage4_report=None, direction_threshold=2.,
        replicates=1000, seed=2026):
    if direction_threshold < 0 or replicates < 1:
        raise ValueError('direction threshold must be nonnegative and replicates positive')
    csv_path=Path(csv_path);metadata_path=Path(metadata_path);out_dir=Path(out_dir)
    meta,profiles=load_profiles(csv_path,metadata_path)
    if stage4_report is not None:
        earlier=json.loads(Path(stage4_report).read_text(encoding='utf-8'))
        if earlier.get('raw_csv_sha256') != sha256_file(csv_path) or earlier.get('raw_metadata_sha256') != sha256_file(metadata_path):
            raise ValueError('stage 4 report hashes do not match supplied source data')
    obs=make_observation_table(profiles)
    targets=build_targets(obs)
    pred,fold=all_model_predictions(obs,targets)
    pred=direction_errors(pred,direction_threshold)
    quality=quality_report(obs,calm_threshold=direction_threshold)
    total=grouped_metrics(pred,['model','information_class','protocol'])
    by_height=grouped_metrics(pred,['model','height_agl_m'])
    by_day=grouped_metrics(pred,['model','date_utc'])
    by_regime=grouped_metrics(reference_speed_bins(pred),['model','ref_speed_bin'])
    paired=paired_day_bootstrap(pred,seed=seed,replicates=replicates)
    forward=temporal_holdout(targets)
    out_dir.mkdir(parents=True,exist_ok=True)
    for file,frame in (
        ('matched_input_residuals.csv',pred), ('model_metrics.csv',total),
        ('by_height.csv',by_height),('by_day.csv',by_day),('by_reference_speed.csv',by_regime),
        ('heldout_day_parameters.csv',fold)):
        frame.to_csv(out_dir/file,index=False)
    charts=make_figures(obs,pred,by_day,by_height,fold,out_dir/'figures')
    result={
        'status':'observed_tower_data_analysis_conditional_on_quality_metadata' if meta['data_kind']=='observed'
                 else 'demonstration_not_field_validation',
        'source':{'provider':meta['provider'],'dataset':meta['dataset_id'],'version':meta['dataset_version'],
                  'station':meta['station_id'],'csv_sha256':sha256_file(csv_path),
                  'metadata_sha256':sha256_file(metadata_path),
                  'source_raw_netcdf_sha256_claim':meta.get('raw_netcdf_sha256')},
        'qa':quality, 'time_blocks':{'days':quality['days'],'timestamps':quality['timestamp_count'],
                                    'heldout_levels_m':[20,40], 'same_time_reference_m':10},
        'protocol':{'primary_information':'wind vector at 10m at the evaluated timestamp only',
                    'cross_validation':'leave_one_UTC_day_out_fit_on_other_days_only; may include future days',
                    'prospective_check':'first ~70 percent of days train; remaining later days evaluated',
                    'extra_sensor_baselines':'use simultaneous 20/40/80m neighboring observations; diagnostic not fair with primary models',
                    'direction_threshold_m_s':direction_threshold,
                    'stability_candidates':'not evaluated as physical stability classes; L not independently measured'},
        'model_metrics':{row['model']:{k:v for k,v in row.items() if k not in ('model','information_class','protocol')}
                         for row in total.to_dict(orient='records')},
        'paired_day_bootstrap':paired, 'chronological_holdout':forward,
        'heldout_day_parameter_ranges':{
            'alpha_min':float(fold.power_alpha.min()),'alpha_max':float(fold.power_alpha.max()),
            'z0_min_m':float(fold.log_roughness_m.min()),'z0_max_m':float(fold.log_roughness_m.max())},
        'figures':charts,
        'limitations':[
            'observations only; no validation of UAV or payload physics',
            'no independent provider signature: downloaded-file hash and stated provider provenance only',
            'KNMI native quality flags and boom-selection metadata not yet independently audited',
            'fixed profile models limited to 10-40m here; no claim about 200m or 500m',
            '7 observed days cannot establish seasonal generalization or precise uncertainty intervals',
            'paired block bootstrap treats held-out-day fits as fixed and does not propagate model-refitting uncertainty',
            'leave-one-day-out uses other days including potentially future periods; chronological holdout is reported separately',
            'extra simultaneous sensors make interpolation comparisons informationally unequal',
            'direction uncertainty at calm speeds is flagged; filtering does not establish instrument correctness',
            'uncalibrated stability-corrected models need flux/Obukhov measurements before physical interpretation',
            'fitted power exponents and roughness are effective empirical parameters, not necessarily physical terrain properties',
        ],
    }
    (out_dir/'stage6_report.json').write_text(json.dumps(result,indent=2,allow_nan=False,default=str),encoding='utf-8')
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--csv',type=Path,default=DEFAULT_CSV)
    p.add_argument('--metadata',type=Path,default=DEFAULT_META)
    p.add_argument('--stage4-report',type=Path,default=None)
    p.add_argument('--out',type=Path,default=DEFAULT_OUT)
    p.add_argument('--direction-threshold',type=float,default=2.)
    p.add_argument('--bootstrap-replicates',type=int,default=1000)
    p.add_argument('--seed',type=int,default=2026)
    a=p.parse_args()
    result=run(a.csv,a.metadata,a.out,a.stage4_report,a.direction_threshold,a.bootstrap_replicates,a.seed)
    print(json.dumps({'status':result['status'],'profiles':result['qa']['timestamp_count'],
                      'days':result['qa']['days'],'model_count':len(result['model_metrics']),
                      'figures':len(result['figures']),'output':str(a.out)},indent=2))

if __name__=='__main__':main()
