'''
Copyright (c) 2024 ABLECLOUD Co. Ltd
이 파일은 Wall VM을 구성할 때 loki와 관련된 설정하는 프로그램입니다.
최초 작성일 : 2024. 10. 07
'''

# !/usr/bin/python3
# -*- coding: utf-8 -*-
import asyncio
import os
import yaml
import argparse
import json
import subprocess
from subprocess import check_output
from subprocess import call
from ablestack import *
import sh

env=os.environ.copy()
env['LANG']="en_US.utf-8"
env['LANGUAGE']="en"

# loki, promtail 서비스 포트
loki_port = ":3100"
promtail_port = ":9080"

'''
함수명 : parseArgs
이 함수는 python library argparse를 시용하여 함수를 실행될 때 필요한 파라미터를 입력받고 파싱하는 역할을 수행합니다.
예를들어 action을 요청하면 해당 action일 때 요구되는 파라미터를 입력받고 해당 코드를 수행합니다.
'''

json_file_path = "/etc/cluster.json"
def parseArgs():
    parser = argparse.ArgumentParser(description='config loki',
                                     epilog='copyrightⓒ 2024 All rights reserved by ABLECLOUD™')

    parser.add_argument('action', choices=[
        'config', 'update'], help='choose one of the actions')
    parser.add_argument('--cube', metavar='name', type=str,
                        nargs='*', help='cube ips')
    parser.add_argument('--ccvm', metavar='name', type=str,
                        nargs='*', help='ccvm ips')
    parser.add_argument('--scvm', metavar='name', type=str,
                        nargs='*', help='scvm ips')

    return parser.parse_args()

def openClusterJson():
    try:
        with open(json_file_path, 'r') as json_file:
            ret = json.load(json_file)
    except Exception as e:
        ret = createReturn(code=500, val='cluster.json read error')
        print ('EXCEPTION : ',e)

    return ret

json_data = openClusterJson()
os_type = json_data["clusterConfig"]["type"]

def ccvmServiceConfig(ccvm_ip):
    ccvm = ccvm_ip.copy()
    for i in range(len(ccvm)):
        ccvm[i] = ccvm[i]
    return ccvm

def cubeServiceConfig(cube_ip):
    cube = cube_ip.copy()
    for i in range(len(cube)):
        cube[i] = cube[i]
    return cube

def scvmServiceConfig(scvm_ip):
    scvm = scvm_ip.copy()
    for i in range(len(scvm)):
        scvm[i] = scvm[i]
    return scvm


# 함수명 : LokiPromtailConfig
# 주요 기능 : 입력 받은 cube, scvm ip의 주소로 promtail.yaml의 job을 각 Hostname으로 변경하고 서비스를 재시작 합니다.

from subprocess import call, Popen, PIPE
import subprocess
import os

def LokiPromtailConfig(ccvm, cube, scvm=None):
    scvm = scvm or []
    promtail_yml_path = '/usr/share/ablestack/ablestack-wall/promtail/'
    # 오류 발생할 경우, 3번 재시도 합니다.
    tries = 3
    for j in range(tries):
        result_code_list = []
        for i in range(len(ccvm)):
            stringOj = ''.join(ccvmServiceConfig(ccvm)[i])
            promtail_config_file = "promtail-ccvm-config.yaml"

            # ccvm 각 항목에 맞는 HOSTNAME 설정
            hostname_cmd = f"ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 root@{stringOj} 'hostname'"
            hostname = check_output(hostname_cmd, shell=True).strip().decode('utf-8')

            # envsubst 명령어 실행 전에 각 ccvm HOSTNAME 환경 변수 전달
            envsubst_cmd = (
                f"export HOSTNAME={hostname} && "  # ccvm의 항목을 HOSTNAME으로 설정
                f"envsubst <{promtail_yml_path}{promtail_config_file} > {promtail_yml_path}temp.yaml && "
                f"mv -f {promtail_yml_path}temp.yaml {promtail_yml_path}promtail-local-config.yaml"
            )

            # subprocess.Popen을 사용하여 명령 실행 및 출력 캡처
            process = Popen(
                ["ssh -o StrictHostKeyChecking=no root@" + stringOj + " '" + envsubst_cmd + "'"],
                universal_newlines=True, shell=True, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT
            )

            stdout, stderr = process.communicate()  # stdout, stderr 캡처
            rc = process.returncode  # 명령어 실행 후 리턴 코드
            result_code_list.append(rc)

            # loki, promtail 서비스 재시작
            service_restart_cmd = (
                'systemctl enable --now loki.service && systemctl enable --now promtail.service'
            )
            # subprocess.Popen을 사용하여 명령 실행 및 출력 캡처
            process = Popen(
                ["ssh -o StrictHostKeyChecking=no root@" + stringOj + " '" + service_restart_cmd + "'"],
                universal_newlines=True, shell=True, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT
            )

            stdout, stderr = process.communicate()  # stdout, stderr 캡처
            rc = process.returncode  # 명령어 실행 후 리턴 코드
            result_code_list.append(rc)

        for i in range(len(cube)):
            stringOj = ''.join(cubeServiceConfig(cube)[i])
            promtail_config_file = "promtail-cube-config.yaml"

            # cube의 각 항목에 맞는 HOSTNAME 설정
            hostname_cmd = f"ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 root@{stringOj} 'hostname'"
            hostname = check_output(hostname_cmd, shell=True).strip().decode('utf-8')

            # envsubst 명령어 실행 전에 각 cube의 HOSTNAME 환경 변수 전달
            envsubst_cmd = (
                f"export HOSTNAME={hostname} && "  # cube의 항목을 HOSTNAME으로 설정
                f"envsubst <{promtail_yml_path}{promtail_config_file} > {promtail_yml_path}temp.yaml && "
                f"mv -f {promtail_yml_path}temp.yaml {promtail_yml_path}promtail-local-config.yaml"
            )

            # subprocess.Popen을 사용하여 명령 실행 및 출력 캡처
            process = Popen(
                ["ssh -o StrictHostKeyChecking=no root@" + stringOj + " '" + envsubst_cmd + "'"],
                universal_newlines=True, shell=True, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT
            )

            stdout, stderr = process.communicate()  # stdout, stderr 캡처
            rc = process.returncode  # 명령어 실행 후 리턴 코드
            result_code_list.append(rc)

            # promtail 서비스 재시작
            service_restart_cmd = (
                'systemctl enable --now promtail.service'
            )

            process = Popen(
                ["ssh -o StrictHostKeyChecking=no root@" + stringOj + " '" + service_restart_cmd + "'"],
                universal_newlines=True, shell=True, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT
            )

            stdout, stderr = process.communicate()  # stdout, stderr 캡처
            rc = process.returncode  # 명령어 실행 후 리턴 코드
            result_code_list.append(rc)

        if os_type == "ablestack-hci":
            for i in range(len(scvm)):
                stringOj = ''.join(scvmServiceConfig(scvm)[i])
                promtail_config_file = "promtail-scvm-config.yaml"

                # scvm 각 항목에 맞는 HOSTNAME 설정
                hostname_cmd = f"ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 root@{stringOj} 'hostname'"
                hostname = check_output(hostname_cmd, shell=True).strip().decode('utf-8')

                # envsubst 명령어 실행 전에 각 scvm HOSTNAME 환경 변수 전달
                envsubst_cmd = (
                    f"export HOSTNAME={hostname} && "  # scvm의 항목을 HOSTNAME으로 설정
                    f"envsubst <{promtail_yml_path}{promtail_config_file} > {promtail_yml_path}temp.yaml && "
                    f"mv -f {promtail_yml_path}temp.yaml {promtail_yml_path}promtail-local-config.yaml"
                )

                # subprocess.Popen을 사용하여 명령 실행 및 출력 캡처
                process = Popen(
                    ["ssh -o StrictHostKeyChecking=no root@" + stringOj + " '" + envsubst_cmd + "'"],
                    universal_newlines=True, shell=True, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT
                )

                stdout, stderr = process.communicate()  # stdout, stderr 캡처
                rc_one = process.returncode  # 명령어 실행 후 리턴 코드

                # promtail 서비스 재시작
                service_restart_cmd = (
                    'systemctl enable --now promtail.service'
                )

                process = Popen(
                    ["ssh -o StrictHostKeyChecking=no root@" + stringOj + " '" + service_restart_cmd + "'"],
                    universal_newlines=True, shell=True, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT
                )

                stdout, stderr = process.communicate()  # stdout, stderr 캡처
                rc_two = process.returncode  # 명령어 실행 후 리턴 코드

                result_code_list.append(rc_one)
                result_code_list.append(rc_two)

        if all(0 == x for x in result_code_list):
            result = 200
        else:
            result = 500

        if result == 500:
            if j < tries - 1:
                continue
            else:
                raise Exception("Command failed after maximum retries")
        break
    return result


# 함수명 : RestartLoki
# 주요 기능 : 입력 받은 ccvm ip의 주소로 loki service를 재시작 합니다.

def RestartLoki(ccvm):
    for i in range(len(ccvm)):
        stringOj = ''.join(ccvmServiceConfig(ccvm)[i])
        os.system("ssh -o StrictHostKeyChecking=no root@" + stringOj + " 'systemctl restart loki.service'")


# 함수명 : RestartLokiPromtail
# 주요 기능 : 입력 받은 ccvm, cube, scvm ip의 주소로 promtail service를 재시작 합니다.

def RestartLokiPromtail(ccvm, cube, scvm=None):
    scvm = scvm or []
    for i in range(len(ccvm)):
        stringOj = ''.join(ccvmServiceConfig(ccvm)[i])
        os.system("ssh -o StrictHostKeyChecking=no root@" + stringOj + " 'systemctl restart loki.service'")
        os.system("ssh -o StrictHostKeyChecking=no root@" + stringOj + " 'systemctl restart promtail.service'")
    for i in range(len(cube)):
        stringOj = ''.join(cubeServiceConfig(cube)[i])
        os.system("ssh -o StrictHostKeyChecking=no root@" + stringOj + " 'systemctl restart promtail.service'")
    if os_type == "ablestack-hci":
        for i in range(len(scvm)):
            stringOj = ''.join(scvmServiceConfig(scvm)[i])
            os.system("ssh -o StrictHostKeyChecking=no root@" + stringOj + " 'systemctl restart promtail.service'")

def main():
    args = parseArgs()

    if (args.action) == 'config':
        try:
            if os_type == "ablestack-hci":
                result = LokiPromtailConfig(args.ccvm, args.cube, args.scvm)
            else:
                result = LokiPromtailConfig(args.ccvm, args.cube)

            if result == 200:
                ret = createReturn(code=200, val="completed loki and promtail configuration")
                print(json.dumps(json.loads(ret), indent=4))
            else:
                ret = createReturn(code=500, val="fail to update loki and promtail configuration")
                print(json.dumps(json.loads(ret), indent=4))
        except Exception as e:
            ret = createReturn(code=500, val="fail to update loki and promtail configuration")
            print(json.dumps(json.loads(ret), indent=4))
    if (args.action) == 'update':
        try:
            if os_type == "ablestack-hci":
                RestartLokiPromtail(args.ccvm, args.cube, args.scvm)
            else:
                RestartLokiPromtail(args.ccvm, args.cube)

            ret = createReturn(code=200, val="updated loki and promtail configuration")
            print(json.dumps(json.loads(ret), indent=4))
        except Exception as e:
            ret = createReturn(code=500, val="fail to update loki and promtail configuration")
            print(json.dumps(json.loads(ret), indent=4))

    return ret

if __name__ == "__main__":
    main()
