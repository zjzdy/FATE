#!/bin/bash
set -e
module_name="federatedml"
cwd=$(cd `dirname $0`; pwd)
cd ${cwd}
source ./configurations.sh

usage() {
	echo "usage: $0 {binary/build} {packaging|config|install|init} {configurations path}."
}

deploy_mode=$1
config_path=$3
if [[ ${config_path} == "" ]] || [[ ! -f ${config_path} ]]
then
	usage
	exit
fi
source ${config_path}

# deploy functions

packaging() {
    source ../../default_configurations.sh
    package_init ${output_packages_dir} ${module_name}
	cp -r ${source_code_dir}/federatedml ${output_packages_dir}/source/${module_name}/
	cp -r ${source_code_dir}/examples ${output_packages_dir}/source/${module_name}
	mkdir -p ${output_packages_dir}/source/${module_name}/arch
	cp -r ${source_code_dir}/arch/api ${output_packages_dir}/source/${module_name}/arch/
	return 0
}

config() {
    config_label=$4
	cd ${output_packages_dir}/config/${config_label}/${module_name}/conf
	python ${cwd}/generate_server_conf.py ${cwd}/service.env.tmp ./server_conf.json
	return 0
}

install () {
    mkdir -p ${deploy_dir}
    cp -r ${deploy_packages_dir}/source/${module_name}/* ${deploy_dir}/
    mkdir -p ${deploy_dir}/arch/conf
    cp -r ${deploy_packages_dir}/config/${module_name}/conf/* ${deploy_dir}/arch/conf/
}

init (){
	return 0
}

case "$2" in
    packaging)
        packaging $*
        ;;
    config)
        config $*
        ;;
    install)
        install $*
        ;;
    init)
        init $*
        ;;
	*)
	    usage
        exit -1
esac
