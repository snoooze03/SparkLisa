#!/usr/bin/env python

import argparse
import shutil
import time
import tarfile
import os
import subprocess
import shlex
import urllib
from datetime import datetime

from snakebite.client import Client


numbers_of_nodes = None
rate = None
window = None
duration = None
number_of_values = None
number_of_files = None
hdfs_path = 'hdfs://diufpc56.unifr.ch:8020/user/stefan/sparkLisa/'
hdfs_client = Client('diufpc56.unifr.ch', 8020, use_trash=False)
# hdfs_path = 'hdfs://localhost:9999/sparkLisa/'
# hdfs_client = Client('localhost', 9999, use_trash=False)
spark_bin_path = '/home/stefan/spark/bin/'
spark_command = spark_bin_path+'spark-submit --class ch.unibnf.mcs.sparklisa.app.{0}' \
                               ' --master yarn-cluster --num-executors {1} --executor-cores 8 ' \
                               '--driver-memory 3584m ' \
                               '../../../target/SparkLisa-0.0.1-SNAPSHOT.jar {2} {3} {4} {5} ' \
                               'hdfs://diufpc56.unifr.ch:8020/user/stefan/sparkLisa/topology/{6} {7} {8}'
log_file_path = '../resources/logs'

date_format = '%d%m%Y%H%M%S'


def parse_arguments():
    parser = argparse.ArgumentParser('Cluster automation for SparkLisa')
    parser.add_argument('rate', metavar='r', type=float, help='Number of values per minute submitted to each node')
    parser.add_argument('window', metavar='w', type=int, help='Window duration in seconds')
    parser.add_argument('duration', metavar='d', type=int, help='Duration after which the Spark Job is terminated')
    parser.add_argument('-r','--repetitions', metavar='rp', type=int, default=1,
                        help='Number of times each stage is run (default 1)')
    parser.add_argument('-m','--mode', metavar='m', type=str, default='s',
                        help='s for spatial, t for temporal, m for spatial with statistical test, '
                             'mtl for temporal with statistical test local, mtg for temporal with statistical test global, '
                             'tt for topology types (default s), mn for naive monte carlo approach')
    parser.add_argument('-bs', '--basestations', metavar='bs', nargs='*', type=int, help='List of numbers af base stations.')
    parser.add_argument('-ks', '--temporal_values', metavar='ks', nargs='*', type=int, help='List of temporal values to be used.')
    parser.add_argument('-nn', '--num_nodes', metavar='tp', nargs='*', type=str, help='Alternative topology file names', default='1600')

    args = vars(parser.parse_args())

    global rate, window, duration, repetitions, mode, base_stations, ks, num_nodes_arg
    rate = args['rate']
    window = args['window']
    duration = args['duration']
    mode = args['mode']
    repetitions = args['repetitions']
    base_stations = args['basestations']
    ks = args['temporal_values']
    num_nodes_arg = args['num_nodes']


def delete_folder_contents(path):
    for root, dirs, files in os.walk(path):
        for f in files:
            os.unlink(os.path.join(root, f))
        for d in dirs:
            shutil.rmtree(os.path.join(root, d))


def cleanup_hdfs(num_nodes, num_base_stations):
    hdfs_client.delete(['sparkLisa/results/{1}_{0}/'.format(num_nodes, num_base_stations)], recurse=True).next()


def collect_and_zip_output(log_file_name, num_base_stations, num_nodes, run_type, k=''):
    output_folder = '../resources/temp/'
    if not os.path.isdir(output_folder): os.makedirs(output_folder)
    if not os.path.isdir(output_folder + 'results/'): os.makedirs(output_folder + 'results/')

    shutil.copyfile(log_file_name, output_folder + log_file_name.split('/')[-1])
    list(hdfs_client.copyToLocal(['sparkLisa/results/{0}_{1}'.format(num_base_stations, num_nodes) + '/'],
                                 output_folder + 'results/'))
    if not 'temporal' in run_type:
        tar_name = '{0}_{1}_{2}_{3}_{4}_{5}_{6}'.format(run_type, num_base_stations, num_nodes, rate, window, duration,
                                                       datetime.now().strftime(date_format))
    else:
        tar_name = '{0}_{1}_{2}_{3}_{4}_{5}_{6}_{7}'.format(run_type, num_base_stations, k, num_nodes, rate, window,
                                                            duration, datetime.now().strftime(date_format))
    create_tar('../resources/', tar_name, '../resources/temp')
    delete_folder_contents('../resources/temp/')
    delete_folder_contents('../resources/topology')
    cleanup_hdfs(num_nodes, num_base_stations)


def create_tar(tar_path, tar_name, path):
    tar_file = tarfile.open(os.path.join(tar_path, tar_name) + '.tar.gz', 'w:gz')
    tar_file.add(path, arcname=tar_name)
    tar_file.close()

def read_yarn_log(proc):
    app_master_host = None
    app_id = None
    while app_id is None or app_master_host is None:
        err_line = proc.stderr.readline()

        if 'application identifier' in err_line:
            id_ = err_line.split(':')[1].strip()
            if id_.startswith('application'):
                app_id = id_

        elif 'appMasterHost' in err_line:
            host = err_line.split(':')[1].strip()
            if host.startswith('diufpc'):
                app_master_host = host

    return app_id, app_master_host

def wait_for_finish(proc):
    status = None
    while status != 'FINISHED':
        err_line = proc.stderr.readline()
        if 'yarnAppState' in err_line:
            status = err_line.split(':')[1].strip()


def run(class_name, base_stations_, topology_type, run_type, k='', random_values='', num_nodes=1600):
    for num_base in base_stations_:
        for _ in range(0, repetitions):
            log_file_name = 'sparklisa_{1}_{0}.log'.format(num_base, run_type)
            log_file = os.path.join(log_file_path, log_file_name)
            topology_file = 'topology_bare_{0}_{1}.txt'.format(topology_type, num_nodes)
            spark_command_ = spark_command.format(
                class_name,
                num_base,
                window,
                rate,
                num_base,
                duration,
                topology_file,
                k,
                random_values
            )
            p = subprocess.Popen(shlex.split(spark_command_), stderr=subprocess.PIPE)
            app_id, app_master_host = read_yarn_log(p)
            app_id_part = app_id.replace('application_', '')
            log_url = 'http://{0}:8042/logs/container/{1}/container_{2}_01_000001/stderr'.format(app_master_host, app_id, app_id_part)
            wait_for_finish(p)
            time.sleep(60)
            urllib.urlretrieve(log_url, log_file)
            collect_and_zip_output(log_file, num_base, num_nodes, run_type, k)

def run_spatial():
    stations = [1,2,4,8,16] if not base_stations else base_stations
    topology_type = 'connected'
    class_name = 'SpatialLisaApp'
    run_type = 'spatial'
    if len(num_nodes_arg) > 0:
        for nb in num_nodes_arg:
            run(class_name, stations, topology_type, run_type, num_nodes=nb)
    else:
        run(class_name, stations, topology_type, run_type)

def run_temporal():
    stations = [1,16] if not base_stations else base_stations
    ks_ = [1,5,10,20,100] if not ks else ks
    topology_type = 'connected'
    class_name = 'TemporalLisaApp'
    run_type = 'temporal'
    for k in ks_:
        run(class_name, stations, topology_type, run_type, k=str(k))

def run_monte_carlo():
    stations = [1,2,4,8,16] if not base_stations else base_stations
    topology_type = 'connected'
    class_name = 'SpatialLisaMonteCarloApp'
    run_type = 'monte_carlo'
    if len(num_nodes_arg) > 0:
        for nb in num_nodes_arg:
            run(class_name, stations, topology_type, run_type, random_values='1000', num_nodes=nb)
        else:
            run(class_name, stations, topology_type, run_type, random_values='1000')


def run_monte_carlo_naive():
    stations = [1,2,4,8,16] if not base_stations else base_stations
    topology_type = 'connected'
    class_name = 'SpatialLisaMonteCarloNaiveApp'
    run_type = 'monte_carlo_naive'
    run(class_name, stations, topology_type, run_type, random_values='1000')


def run_temporal_monte_carlo_local():
    stations = [16] if not base_stations else base_stations
    ks_ = [1,2,5,10,20] if not ks else ks
    topology_type = 'connected'
    class_name = 'TemporalLisaMonteCarloLocalApp'
    run_type = 'monte_carlo_temporal_local'
    for k in ks_:
        run(class_name, stations, topology_type, run_type, k=str(k), random_values='1000')


def run_temporal_monte_carlo_global():
    stations = [16] if not base_stations else base_stations
    ks_ = [1,2,5,10,20] if not ks else ks
    topology_type = 'connected'
    class_name = 'TemporalLisaMonteCarloGlobalApp'
    run_type = 'monte_carlo_temporal_global'
    for k in ks_:
        run(class_name, stations, topology_type, run_type, k=str(k), random_values='1000')

def run_topology_types():
    stations = [16] if not base_stations else base_stations
    class_name = 'SpatialLisaMonteCarloApp'
    run_type = 'topologies'
    for topology_type in ['sparse', 'connected', 'dense']:
        if len(num_nodes_arg) == 1:
            run(class_name, stations, topology_type, run_type, random_values='1000', num_nodes=num_nodes_arg[0])
        else:
            run(class_name, stations, topology_type, run_type, random_values='1000')

def main():
    parse_arguments()

    if not os.path.isdir(log_file_path):
        os.makedirs(log_file_path)

    os.environ['HADOOP_CONF_DIR'] = '/etc/hadoop/conf'

    switch = {
        's': run_spatial,
        't': run_temporal,
        'm': run_monte_carlo,
        'mtl': run_temporal_monte_carlo_local,
        'mtg': run_temporal_monte_carlo_global,
        'tt': run_topology_types,
        'mn': run_monte_carlo_naive
    }

    switch[mode]()



main()