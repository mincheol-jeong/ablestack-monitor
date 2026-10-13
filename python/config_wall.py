'''
Copyright (c) 2021 ABLECLOUD Co. Ltd
이 파일은 Wall VM을 구성할 때 prometheus.yml, defaults.ini, db 파일 등을 설정하는 프로그램입니다.
최초 작성일 : 2021. 08. 25
'''

#!/usr/bin/python3
# -*- coding: utf-8 -*-

import yaml
import argparse
import json
import os
import sh
from ablestack import *
import configparser
import sqlite3
import re
import pymysql
import sys
from sh import cp
from sh import systemctl
from sh import ssh
from sh import python3
from sh import Command
from sh import ErrorReturnCode

# prometheus에서 수집하는 exporter 및 서비스 포트
wall_prometheus_port = ":3001"
libvirt_exporter_port = ":3002"
node_exporter_port = ":3003"
process_exporter_port = ":3004"
blackbox_exporter_port = ":3005"
ipmi_exporter_port = ":3006"
license_exporter_port = ":3007"
cube_service_port = ":9090"
mold_service_port = ":8080"
mold_db_port = ":3306"
glue_prometheus_port = ":9095"

ROOT_CA_CERT_PATH = "/usr/share/ablestack/ablestack-wall/grafana/tls/rootCA.crt"
OS_TRUST_ANCHOR_PATH = "/etc/pki/ca-trust/source/anchors/ablestack-rootca.crt"
JAVA_TRUSTSTORE_PATH = "/etc/pki/java/cacerts"
JAVA_TRUSTSTORE_PASSWORD = "changeit"
JAVA_TRUSTSTORE_ALIAS = "ablestack-wall"

def logWallError(action, error, detail=""):
    message = str(error).replace("\n", " ")
    if len(message) > 1000:
        message = message[:1000] + "..."
    prefix = f">> [WALL][{action}]"
    if detail:
        prefix += f" {detail}"
    sys.stderr.write(f"{prefix}: {type(error).__name__}: {message}\n")

'''
함수명 : parseArgs
이 함수는 python library argparse를 시용하여 함수를 실행될 때 필요한 파라미터를 입력받고 파싱하는 역할을 수행합니다.
예를들어 action을 요청하면 해당 action일 때 요구되는 파라미터를 입력받고 해당 코드를 수행합니다.
'''

json_file_path = "/etc/cluster.json"
def parseArgs():
    parser = argparse.ArgumentParser(description='Prometheus Yaml file parsing and replace targets',
                                     epilog='copyrightⓒ 2021 All rights reserved by ABLECLOUD™')

    parser.add_argument('action', choices=[
                        'config', 'update', 'glueDsUpdate'], help='choose one of the actions')
    parser.add_argument('--cube', metavar='name', type=str,
                        nargs='*', help='cube ips')
    parser.add_argument('--scvm', metavar='name', type=str,
                        nargs='*', help='scvm ips')
    parser.add_argument('--ccvm', metavar='name', type=str,
                        nargs='*', help='ccvm ips')

    return parser.parse_args()

def openClusterJson():
    try:
        with open(json_file_path, 'r') as json_file:
            ret = json.load(json_file)
    except Exception as e:
        ret = createReturn(code=500, val='cluster.json read error')
        logWallError("cluster-json", e, json_file_path)

    return ret

json_data = openClusterJson()
os_type = json_data["clusterConfig"]["type"]

def cubeServiceConfig(cube_ip):
    cube = cube_ip.copy()
    for i in range(len(cube)):
        cube[i] = cube[i] + cube_service_port
    return cube


def moldServiceConfig(ccvm_ip):
    ccvm = ccvm_ip.copy()
    for i in range(len(ccvm)):
        ccvm[i] = ccvm[i] + mold_service_port
    return ccvm


def moldDBConfig(ccvm_ip):
    ccvm = ccvm_ip.copy()
    for i in range(len(ccvm)):
        ccvm[i] = ccvm[i] + mold_db_port
    return ccvm


def libvirtConfig(cube_ip):
    cube = cube_ip.copy()
    for i in range(len(cube)):
        cube[i] = cube[i] + libvirt_exporter_port
    return cube


def cubeNodeConfig(cube_ip):
    cube = cube_ip.copy()
    for i in range(len(cube)):
        cube[i] = cube[i] + node_exporter_port
    return cube

def ipmiConfig(cube_ip):
    cube = cube_ip.copy()
    for i in range(len(cube)):
        cube[i] = cube[i] + ipmi_exporter_port
    return cube

def appendPort(ip_list, port):
    targets = ip_list.copy()
    for i in range(len(targets)):
        targets[i] = targets[i] + port
    return targets

def scvmNodeConfig(scvm_ip):
    scvm = scvm_ip.copy()
    for i in range(len(scvm)):
        scvm[i] = scvm[i] + node_exporter_port
    return scvm

def ccvmNodeConfig(ccvm_ip):
    ccvm = ccvm_ip.copy()
    for i in range(len(ccvm)):
        ccvm[i] = ccvm[i] + node_exporter_port
    return ccvm

def hostLicenseConfig(cube_ip):
    return appendPort(cube_ip, license_exporter_port)


def wallPrometheusConfig(ccvm_ip):
    ccvm = ccvm_ip.copy()
    for i in range(len(ccvm)):
        ccvm[i] = ccvm[i] + wall_prometheus_port
    return ccvm


def gluePrometheusConfig(scvm_ip):
    scvm = scvm_ip.copy()
    for i in range(len(scvm)):
        scvm[i] = scvm[i] + glue_prometheus_port
    return scvm


def cubeProcessConfig(cube_ip):
    cube = cube_ip.copy()
    for i in range(len(cube)):
        cube[i] = cube[i] + process_exporter_port
    return cube


def scvmProcessConfig(scvm_ip):
    scvm = scvm_ip.copy()
    for i in range(len(scvm)):
        scvm[i] = scvm[i] + process_exporter_port
    return scvm


def ccvmProcessConfig(ccvm_ip):
    ccvm = ccvm_ip.copy()
    for i in range(len(ccvm)):
        ccvm[i] = ccvm[i] + process_exporter_port
    return ccvm


def cubeBlackboxConfig(cube_ip):
    cube = cube_ip.copy()
    for i in range(len(cube)):
        cube[i] = cube[i]
    return cube


def scvmBlackboxConfig(scvm_ip):
    scvm = scvm_ip.copy()
    for i in range(len(scvm)):
        scvm[i] = scvm[i]
    return scvm

def ccvmBlackboxConfig(ccvm_ip):
    ccvm = ccvm_ip.copy()
    for i in range(len(ccvm)):
        ccvm[i] = ccvm[i]
    return ccvm

def ccvmBlackboxConfigReplacement(ccvm_ip):
    ccvm = ccvm_ip.copy()
    for i in range(len(ccvm)):
        ccvm[i] = ccvm[i] + blackbox_exporter_port
    return ccvm


def ensureScrapeJob(prometheus_org, job_name, static_targets):
    scrape_configs = prometheus_org.get('scrape_configs', [])
    for scrape_config in scrape_configs:
        if scrape_config.get('job_name') == job_name:
            scrape_config['static_configs'][0]['targets'] = static_targets
            return

    scrape_configs.append({
        'job_name': job_name,
        'static_configs': [{'targets': static_targets}]
    })

# 함수명 : configYaml
# 주요 기능 : 입력 받은 ip를 prometheus.yml 파일의 targets에 설정


def configYaml(cube, ccvm, scvm=None):
    scvm = scvm or []
    prometheus_yml_path = '/usr/share/ablestack/ablestack-wall/prometheus/prometheus.yml'

    with open(prometheus_yml_path) as f:
        prometheus_org = yaml.safe_load(f)
    for i in range(len(prometheus_org['scrape_configs'])):

        if os_type == "ablestack-hci":
            if prometheus_org['scrape_configs'][i]['job_name'] == 'libvirt':
                prometheus_org['scrape_configs'][i]['static_configs'][0]['targets'] = libvirtConfig(
                    cube)

            elif prometheus_org['scrape_configs'][i]['job_name'] == 'cube':
                prometheus_org['scrape_configs'][i]['static_configs'][0]['targets'] = cubeNodeConfig(
                    cube)

            elif prometheus_org['scrape_configs'][i]['job_name'] == 'ipmi':
                prometheus_org['scrape_configs'][i]['static_configs'][0]['targets'] = ipmiConfig(
                    cube)

            elif prometheus_org['scrape_configs'][i]['job_name'] == 'scvm':
                prometheus_org['scrape_configs'][i]['static_configs'][0]['targets'] = scvmNodeConfig(
                    scvm)

            elif prometheus_org['scrape_configs'][i]['job_name'] == 'ccvm':
                prometheus_org['scrape_configs'][i]['static_configs'][0]['targets'] = ccvmNodeConfig(
                    ccvm)

            elif prometheus_org['scrape_configs'][i]['job_name'] == 'cube-process-exporter':
                prometheus_org['scrape_configs'][i]['static_configs'][0]['targets'] = cubeProcessConfig(
                    cube)

            elif prometheus_org['scrape_configs'][i]['job_name'] == 'scvm-process-exporter':
                prometheus_org['scrape_configs'][i]['static_configs'][0]['targets'] = scvmProcessConfig(
                    scvm)

            elif prometheus_org['scrape_configs'][i]['job_name'] == 'ccvm-process-exporter':
                prometheus_org['scrape_configs'][i]['static_configs'][0]['targets'] = ccvmProcessConfig(
                    ccvm)

            elif prometheus_org['scrape_configs'][i]['job_name'] == 'cube-blackbox':
                prometheus_org['scrape_configs'][i]['static_configs'][0]['targets'] = cubeBlackboxConfig(
                    cube)
                prometheus_org['scrape_configs'][i]['relabel_configs'][-1]['replacement'] = ccvmBlackboxConfigReplacement(
                    ccvm)[0]

            elif prometheus_org['scrape_configs'][i]['job_name'] == 'scvm-blackbox':
                prometheus_org['scrape_configs'][i]['static_configs'][0]['targets'] = scvmBlackboxConfig(
                    scvm)
                prometheus_org['scrape_configs'][i]['relabel_configs'][-1]['replacement'] = ccvmBlackboxConfigReplacement(
                    ccvm)[0]

            elif prometheus_org['scrape_configs'][i]['job_name'] == 'ccvm-blackbox':
                prometheus_org['scrape_configs'][i]['static_configs'][0]['targets'] = ccvmBlackboxConfig(
                    ccvm)
                prometheus_org['scrape_configs'][i]['relabel_configs'][-1]['replacement'] = ccvmBlackboxConfigReplacement(
                    ccvm)[0]

            elif prometheus_org['scrape_configs'][i]['job_name'] == 'blackbox-tcp':
                prometheus_org['scrape_configs'][i]['static_configs'][0]['targets'] = cubeServiceConfig(cube) + moldServiceConfig(ccvm) + moldDBConfig(ccvm) + libvirtConfig(cube) + cubeNodeConfig(cube) + ipmiConfig(cube) + scvmNodeConfig(scvm) + ccvmNodeConfig(
                    ccvm) + cubeProcessConfig(cube) + scvmProcessConfig(scvm) + ccvmProcessConfig(ccvm) + ccvmBlackboxConfigReplacement(ccvm)
                prometheus_org['scrape_configs'][i]['relabel_configs'][-1]['replacement'] = ccvmBlackboxConfigReplacement(
                    ccvm)[0]
        else :
            if prometheus_org['scrape_configs'][i]['job_name'] == 'libvirt':
                prometheus_org['scrape_configs'][i]['static_configs'][0]['targets'] = libvirtConfig(
                    cube)

            elif prometheus_org['scrape_configs'][i]['job_name'] == 'cube':
                prometheus_org['scrape_configs'][i]['static_configs'][0]['targets'] = cubeNodeConfig(
                    cube)

            elif prometheus_org['scrape_configs'][i]['job_name'] == 'ipmi':
                prometheus_org['scrape_configs'][i]['static_configs'][0]['targets'] = ipmiConfig(
                    cube)

            elif prometheus_org['scrape_configs'][i]['job_name'] == 'ccvm':
                prometheus_org['scrape_configs'][i]['static_configs'][0]['targets'] = ccvmNodeConfig(
                    ccvm)

            elif prometheus_org['scrape_configs'][i]['job_name'] == 'cube-process-exporter':
                prometheus_org['scrape_configs'][i]['static_configs'][0]['targets'] = cubeProcessConfig(
                    cube)

            elif prometheus_org['scrape_configs'][i]['job_name'] == 'ccvm-process-exporter':
                prometheus_org['scrape_configs'][i]['static_configs'][0]['targets'] = ccvmProcessConfig(
                    ccvm)

            elif prometheus_org['scrape_configs'][i]['job_name'] == 'cube-blackbox':
                prometheus_org['scrape_configs'][i]['static_configs'][0]['targets'] = cubeBlackboxConfig(
                    cube)
                prometheus_org['scrape_configs'][i]['relabel_configs'][-1]['replacement'] = ccvmBlackboxConfigReplacement(
                    ccvm)[0]

            elif prometheus_org['scrape_configs'][i]['job_name'] == 'ccvm-blackbox':
                prometheus_org['scrape_configs'][i]['static_configs'][0]['targets'] = ccvmBlackboxConfig(
                    ccvm)
                prometheus_org['scrape_configs'][i]['relabel_configs'][-1]['replacement'] = ccvmBlackboxConfigReplacement(
                    ccvm)[0]

            elif prometheus_org['scrape_configs'][i]['job_name'] == 'blackbox-tcp':
                prometheus_org['scrape_configs'][i]['static_configs'][0]['targets'] = cubeServiceConfig(cube) + moldServiceConfig(ccvm) + moldDBConfig(ccvm) + libvirtConfig(cube) + cubeNodeConfig(cube) + ipmiConfig(cube) + ccvmNodeConfig(
                    ccvm) + cubeProcessConfig(cube)  + ccvmProcessConfig(ccvm) + ccvmBlackboxConfigReplacement(ccvm)
                prometheus_org['scrape_configs'][i]['relabel_configs'][-1]['replacement'] = ccvmBlackboxConfigReplacement(
                    ccvm)[0]
    ensureScrapeJob(prometheus_org, 'host-license', hostLicenseConfig(cube))

    with open(prometheus_yml_path, 'w') as yaml_file:
        yaml_file.write(
            yaml.dump(prometheus_org, default_flow_style=False))

# 함수명 : configIni
# 주요 기능 : grafana의 설정 파일에 도메인을 ccvm ip로 설정


def configIni(ccvm):
    ini_file = '/usr/share/ablestack/ablestack-wall/grafana/conf/defaults.ini'
    config = configparser.ConfigParser()

    config.read(ini_file)

    config.set('server', 'domain', ccvm[0])

    with open(ini_file, 'w') as f:
        config.write(f)


def configDS(scvm=None):  # 기본값 None 추가
    conn = sqlite3.connect(
        "/usr/share/ablestack/ablestack-wall/grafana/data/grafana.db")

    ds_update_query1 = "UPDATE data_source SET url = \'http://" + \
        "localhost:3001' WHERE name = 'Wall'"

    if os_type == "ablestack-hci" and scvm:
        ds_update_query2 = "UPDATE data_source SET url = \'http://" + \
            gluePrometheusConfig(scvm)[0] + "' WHERE name = 'Glue'"

        glue_prometheus_ip = findGluePrometheusIp()
        if glue_prometheus_ip != "":
            ds_update_query2 = "UPDATE data_source SET url = \'http://" + \
                glue_prometheus_ip + glue_prometheus_port + "' WHERE name = 'Glue'"

    ds_update_query3 = "UPDATE data_source SET url = \'" + \
        "localhost:3306' WHERE name = 'Mold'"

    ds_update_query4 = "UPDATE data_source SET url = \'http://" + \
        "localhost:3001' WHERE name = 'Wall' AND org_id = '2'"

    ds_update_query5 = "UPDATE data_source SET url = \'https://" + \
            "ccvm:8081' WHERE name = 'yesoreyeram-infinity-datasource'"

    cur = conn.cursor()
    cur.execute(ds_update_query1)
    if os_type == "ablestack-hci" and scvm:
        cur.execute(ds_update_query2)
    cur.execute(ds_update_query3)
    cur.execute(ds_update_query4)
    cur.execute(ds_update_query5)

    conn.commit()
    conn.close()

    exist_yn = os.system("crontab -l |grep 'config_wall.py glueDsUpdate' > /dev/null")
    if exist_yn != 0:
        os.system("echo -e \'*/5 * * * * /usr/bin/python3 /usr/share/ablestack/ablestack-wall/python/config_wall.py glueDsUpdate \' >> /var/spool/cron/root")


def configSkydiveLink(ccvm):
    ccvm_ip = ccvm[0] if isinstance(ccvm, (list, tuple)) else str(ccvm)

    conn = sqlite3.connect("/usr/share/ablestack/ablestack-wall/grafana/data/grafana.db")
    cur = conn.cursor()

    cur.execute("SELECT id, data FROM dashboard WHERE org_id = 1 AND data LIKE '%:8082%'")
    rows = cur.fetchall()

    # 수정 1: https? 를 사용하여 http:// 와 https:// 모두 매칭되도록 변경
    pattern = re.compile(r"https?://(?:\d{1,3}\.){3}\d{1,3}:8082(?P<tail>[^\"'\s]*)")

    # 수정 2: 치환될 결과를 무조건 https:// 로 고정
    replacement = rf"https://{ccvm_ip}:8082\g<tail>"

    updated = 0
    for id_, data in rows:
        if data is None:
            continue
        # bytes → str 디코딩
        if isinstance(data, (bytes, bytearray)):
            try:
                data_str = data.decode('utf-8')
            except UnicodeDecodeError:
                data_str = data.decode('latin-1', 'ignore')  # 최후의 보루
        else:
            data_str = data

        new_data, count = pattern.subn(replacement, data_str)
        if count > 0 and new_data != data_str:
            cur.execute("UPDATE dashboard SET data = ? WHERE id = ?", (new_data, id_))
            updated += 1

    conn.commit()
    conn.close()


def configMoldUserDashboard():
    # grafana.db 에서 사용자 대시보드의 UID 가져오기
    conn = sqlite3.connect(
        "/usr/share/ablestack/ablestack-wall/grafana/data/grafana.db")

    user_dashboard_query = "SELECT uid, slug FROM dashboard WHERE title = '가상머신 상세 현황' AND org_id = 1"

    cur = conn.cursor()
    cur.execute(user_dashboard_query)
    user_dashboard_val = cur.fetchone()

    uri_val = '/d/' + user_dashboard_val[0] + '/' + user_dashboard_val[1] + '?kiosk'

    conn.close()

    cloud_db = pymysql.connect(
        user='cloud',
        password='Ablecloud1!',
        host='localhost',
        db='cloud',
        charset='utf8'
    )

    cursor = cloud_db.cursor(pymysql.cursors.DictCursor)
    update_user_dashboard_uri_sql = "UPDATE configuration SET value ='" + uri_val + "' WHERE name = 'monitoring.wall.portal.vm.uri'"
    cursor.execute(update_user_dashboard_uri_sql)

    cloud_db.commit()
    cloud_db.close()


def configTrustStore():
    if not os.path.exists(ROOT_CA_CERT_PATH):
        raise FileNotFoundError(ROOT_CA_CERT_PATH)

    cp("-f", ROOT_CA_CERT_PATH, OS_TRUST_ANCHOR_PATH)
    Command("update-ca-trust")()

    keytool = Command("keytool")
    try:
        keytool(
            "-delete",
            "-alias", JAVA_TRUSTSTORE_ALIAS,
            "-keystore", JAVA_TRUSTSTORE_PATH,
            "-storepass", JAVA_TRUSTSTORE_PASSWORD
        )
    except ErrorReturnCode:
        pass

    keytool(
        "-importcert",
        "-noprompt",
        "-alias", JAVA_TRUSTSTORE_ALIAS,
        "-file", ROOT_CA_CERT_PATH,
        "-keystore", JAVA_TRUSTSTORE_PATH,
        "-storepass", JAVA_TRUSTSTORE_PASSWORD
    )

# DB 파일 초기화 (기존 초기 파일로 되돌리기)
def initDB():
    hci_types = ["ablestack-hci", "ablestack-hci-filesystem"]

    if os_type in hci_types:
        cp("-f", "/usr/share/ablestack/ablestack-wall/grafana/data/grafana_org.db",
           "/usr/share/ablestack/ablestack-wall/grafana/data/grafana.db")
    else:
        # 그 외의 경우 gfs용 DB 사용
        cp("-f", "/usr/share/ablestack/ablestack-wall/grafana/data/grafana_gfs.db",
           "/usr/share/ablestack/ablestack-wall/grafana/data/grafana.db")

    # WAL/SHM 파일 제거
    try:
        os.remove("/usr/share/ablestack/ablestack-wall/grafana/data/grafana.db-wal")
    except FileNotFoundError:
        pass
    try:
        os.remove("/usr/share/ablestack/ablestack-wall/grafana/data/grafana.db-shm")
    except FileNotFoundError:
        pass

def gluePrometheusIpUpdate():
    conn = sqlite3.connect(
            "/usr/share/ablestack/ablestack-wall/grafana/data/grafana.db")

    select_query = "select url from data_source WHERE name = 'Glue'"

    cur = conn.cursor()
    cur.execute(select_query)

    crrent_ip = cur.fetchone()
    if crrent_ip is not None:
        glue_prometheus_ip = findGluePrometheusIp()
        if glue_prometheus_ip != "" and glue_prometheus_ip not in crrent_ip[0]:
            glue_ds_update_query = "UPDATE data_source SET url = \'http://" + \
                glue_prometheus_ip+glue_prometheus_port + "' WHERE name = 'Glue'"

            cur.execute(glue_ds_update_query)

    conn.commit()
    conn.close()

def findGluePrometheusIp():
    return ssh('-o', 'StrictHostKeyChecking=no', '-o', 'ConnectTimeout=5', "ablecube", "grep $(ceph orch ps |grep prometheus | awk '{print $2 \"-mngt\"}') /etc/hosts | awk '{print $1}'" ).strip()

def ensureRemoteServices(hosts, services):
    if hosts is None:
        return

    service_args = " ".join(services)
    command = "systemctl daemon-reload && systemctl enable --now " + service_args + " && systemctl restart " + service_args
    for host in hosts:
        try:
            ssh('-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=no', '-o', 'ConnectTimeout=5', host, command).strip()
        except Exception as e:
            logWallError("remote-service", e, host + " " + service_args)
            raise

def ensureScvmProcessConfig(scvm):
    if scvm is None:
        return

    for scvm_ip in scvm:
        try:
            result = ssh('-o','StrictHostKeyChecking=no','-o','ConnectTimeout=5', scvm_ip, '/usr/bin/ls /usr/share/ablestack/ablestack-wall/process-exporter/').splitlines()
            if 'scvm_process.yml' in result:
                ssh('-o', 'StrictHostKeyChecking=no', '-o', 'ConnectTimeout=5', scvm_ip, "\cp -f /usr/share/ablestack/ablestack-wall/process-exporter/scvm_process.yml /usr/share/ablestack/ablestack-wall/process-exporter/process.yml").strip()
                ssh('-o', 'StrictHostKeyChecking=no', '-o', 'ConnectTimeout=5', scvm_ip, "rm -f /usr/share/ablestack/ablestack-wall/process-exporter/scvm_process.yml").strip()
        except Exception as e:
            logWallError("scvm-process-config", e, scvm_ip)
            raise

def configLokiPromtail(ccvm, cube, scvm=None):
    try:
        if os_type == "ablestack-hci" and scvm:
            result = json.loads(sh.python3("/usr/share/ablestack/ablestack-wall/python/config_loki.py", "config", "--ccvm", ccvm, "--cube", cube, "--scvm", scvm))
        else:
            result = json.loads(sh.python3("/usr/share/ablestack/ablestack-wall/python/config_loki.py", "config", "--ccvm", ccvm, "--cube", cube))
    except Exception as e:
        logWallError("loki-promtail", e)
        raise

    if result["code"] != 200:
        error = Exception("fail to update loki and promtail : " + result["val"])
        logWallError("loki-promtail", error)
        raise error

def checkPrometheusConfig():
    try:
        promtool = Command("/usr/share/ablestack/ablestack-wall/prometheus/promtool")
        promtool("check", "config", "/usr/share/ablestack/ablestack-wall/prometheus/prometheus.yml")
    except Exception as e:
        logWallError("prometheus-check", e)
        raise

def updateNetdive(ccvm, cube):
    try:
        netdive_result = json.loads(sh.python3("/usr/share/ablestack/ablestack-wall/python/config_netdive.py", "config", "--ccvm", ccvm, "--cube", cube))
        if netdive_result["code"] != 200:
            warning = "fail to update netdive : " + netdive_result["val"]
            sys.stderr.write(">> [WALL][netdive-warning] " + warning + "\n")
            return warning
    except Exception as e:
        warning = "fail to update netdive : " + str(e)
        logWallError("netdive-warning", e)
        return warning

    return ""

def main():
    args = parseArgs()
    if (args.action) == 'config':
        if os_type == "ablestack-hci":
            try:
                os.system("rm -rf cd /nfs/prometheus/ > /dev/null")
                configTrustStore()
                initDB()
                configYaml(args.cube, args.ccvm, args.scvm)
                configIni(args.ccvm)
                configDS(args.scvm)
                configSkydiveLink(args.ccvm)
                configMoldUserDashboard()

                configLokiPromtail(args.ccvm, args.cube, args.scvm)

                ret = createReturn(code=200, val="success wall configuration")
                print(json.dumps(json.loads(ret), indent=4))
            except Exception as e:
                logWallError("config", e, "hci")
                ret = createReturn(code=500, val="fail to configuration")
                print(json.dumps(json.loads(ret), indent=4))
        else:
            try:
                configTrustStore()
                initDB()
                configYaml(args.cube, args.ccvm)
                configIni(args.ccvm)
                configDS()
                configSkydiveLink(args.ccvm)
                configMoldUserDashboard()

                json.loads(sh.python3("/usr/share/ablestack/ablestack-wall/python/config_loki.py","config", "--ccvm", args.ccvm, "--cube", args.cube))

                systemctl('stop', "grafana-server")

                systemctl('enable', '--now', "blackbox-exporter")
                systemctl('enable', '--now', "node-exporter")
                systemctl('enable', '--now', "grafana-server")
                systemctl('enable', '--now', "prometheus")
                systemctl('enable', '--now', "process-exporter")
                systemctl('enable', '--now', "netdive-analyzer")

                systemctl('restart', "grafana-server")
                systemctl('restart', '--now', "prometheus")

                ret = createReturn(code=200, val="success wall configuration")
                print(json.dumps(json.loads(ret), indent=4))
            except Exception as e:
                logWallError("config", e, os_type)
                ret = createReturn(code=500, val="fail to configuration")
                print(json.dumps(json.loads(ret), indent=4))
    if (args.action) == 'update':
        try:
            configYaml(args.cube, args.ccvm, args.scvm)

            ensureRemoteServices(args.cube, [
                "node-exporter.service",
                "process-exporter.service",
                "libvirt-exporter.service",
                "license-exporter.service",
                "promtail.service"
            ])

            if os_type == "ablestack-hci":
                ensureScvmProcessConfig(args.scvm)
                ensureRemoteServices(args.scvm, [
                    "node-exporter.service",
                    "process-exporter.service",
                    "promtail.service"
                ])

            configLokiPromtail(args.ccvm, args.cube, args.scvm)
            checkPrometheusConfig()
            systemctl('restart', 'prometheus')

            netdive_warning = updateNetdive(args.ccvm, args.cube)
            if netdive_warning:
                ret = createReturn(code=200, val="success wall update. warning: " + netdive_warning)
            else:
                ret = createReturn(code=200, val="success wall update")
            print(json.dumps(json.loads(ret), indent=4))
        except Exception as e:
            logWallError("update", e)
            ret = createReturn(code=500, val="fail to update wall : " + str(e))
            print(json.dumps(json.loads(ret), indent=4))
    if (args.action) == 'glueDsUpdate':
        try:
            gluePrometheusIpUpdate()
            ret = createReturn(code=200, val="success Glue prometheus ip update")
            print(json.dumps(json.loads(ret), indent=4))
        except Exception as e:
            logWallError("glue-ds-update", e)
            ret = createReturn(code=500, val="fail to update Glue prometheus ip : " + str(e))
            print(json.dumps(json.loads(ret), indent=4))

    return ret

if __name__ == "__main__":
    main()
