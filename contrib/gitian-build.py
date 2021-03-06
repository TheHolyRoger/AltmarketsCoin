#!/usr/bin/env python3
# Copyright (c) 2018-2019 The Bitcoin Core developers
# Copyright (c) 2018-2020 The AltmarketsCoin Core developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or http://www.opensource.org/licenses/mit-license.php.

import argparse
import os
import subprocess
import sys

def InstallGitianLXC():
    writeFiles = [{
        "path": "/etc/sudoers.d/gitian-lxc",
        "lines": [
            "%sudo ALL=NOPASSWD: /usr/bin/lxc-start",
            "%sudo ALL=NOPASSWD: /usr/bin/lxc-execute"
        ]
    }, {
        "path": "/etc/rc.local",
        "lines": [
            "#!/bin/sh -e",
            "brctl addbr br0",
            "ip addr add 10.0.3.2/24 broadcast 10.0.3.255 dev br0",
            "ip link set br0 up",
            "firewall-cmd --zone=trusted --add-interface=br0",
            "exit 0"
        ]
    }]
    NeedsReboot = False

    for one_file in writeFiles:
        FileNeedsWrite = True
        FileExists = False
        if os.path.exists(one_file["path"]):
            FileExists = True
            with open(one_file["path"], "r") as fHandle:
                CurLines = fHandle.readlines()
            for line in CurLines:
                if one_file["lines"][1] in line or (len(one_file["lines"]) > 2 and one_file["lines"][3] in line):
                    FileNeedsWrite = False
                    break
        if FileNeedsWrite is True:
            NeedsReboot = True
            print("Updating %s" % (one_file["path"]))
            with open(one_file["path"], "a+") as fHandle:
                if FileExists is True:
                    fHandle.write("\n")
                for line in one_file["lines"]:
                    fHandle.write("%s\n" % (line))
            if "rc.local" in one_file["path"]:
                subprocess.check_call(['chmod', '+x', one_file["path"]])
    if NeedsReboot is True:
        print('Reboot is required')
        sys.exit(0)

def InstallVMBuilder():
    vmbuilder_fileName = 'vm-builder_0.12.4+bzr494'
    vmbuilder_fileNameTar = '%s.orig.tar.gz' % (vmbuilder_fileName)
    vmbuilder_url = 'http://archive.ubuntu.com/ubuntu/pool/universe/v/vm-builder/%s' % (vmbuilder_fileNameTar)
    vmbuilder_hash = '76cbf8c52c391160b2641e7120dbade5afded713afaa6032f733a261f13e6a8e'

    previousDir = os.getcwd()
    os.chdir(os.path.expanduser("~"))
    subprocess.call(['wget', vmbuilder_url])
    subprocess.check_call('echo "%s %s" | sha256sum -c' % (vmbuilder_hash, vmbuilder_fileNameTar), shell=True)
    subprocess.call(['tar', '-zxvf', vmbuilder_fileNameTar])
    os.chdir(vmbuilder_fileName.replace("_","-"))
    subprocess.call(['echo', 'sudo', 'python3', 'setup.py', 'install'])
    os.chdir(previousDir)

def setup():
    global args, workdir
    if not args.docker and not args.kvm:
        InstallGitianLXC()
    programs = ['ruby', 'git', 'make', 'wget', 'curl']
    if args.wipe_cache:
        try:
            PathsToClear = []
            PathsToClear += ['gitian-builder/base-trusty-amd64']
            PathsToClear += ['gitian-builder/target-trusty-amd64', 'gitian-builder/build/*', 'gitian-builder/cache/*']
            PathsToClear += ['gitian-builder/inputs/AltmarketsCoin', 'gitian-builder/result/*', 'gitian-builder/var/*', 'gitian.sigs.altmarkets']
            PathsToClear += ['altmarkets-detached-sigs', 'altmarkets-binaries', 'AltmarketsCoin', 'gitian-builder/inputs/*-unsigned.tar.gz']
            PathsToClear = ' '.join(PathsToClear)
            subprocess.check_call('rm -r '+PathsToClear, shell=True)
        except:
            pass
    if args.kvm:
        programs += ['apt-cacher-ng', 'python-vm-builder', 'qemu-kvm', 'qemu-utils']
    elif args.docker and not os.path.isfile('/lib/systemd/system/docker.service'):
        dockers = ['docker.io', 'docker-ce']
        for i in dockers:
            return_code = subprocess.call(['sudo', 'apt-get', 'install', '-qq', i])
            if return_code == 0:
                break
        if return_code != 0:
            print('Cannot find any way to install Docker.', file=sys.stderr)
            sys.exit(1)
    else:
        programs += ['apt-cacher-ng', 'lxc', 'debootstrap']
        programs += ['python-cheetah', 'parted', 'kpartx', 'bridge-utils', 'ubuntu-archive-keyring', 'firewalld' ]
    subprocess.check_call(['sudo', 'apt-get', 'install', '-qq'] + programs)
    if not os.path.isdir('gitian.sigs.altmarkets'):
        subprocess.check_call(['git', 'clone', 'https://github.com/altmarkets/gitian.sigs.altmarkets.git'])
    if not os.path.isdir('altmarkets-detached-sigs'):
        subprocess.check_call(['git', 'clone', 'https://github.com/altmarkets/altmarkets-detached-sigs.git'])
    if not os.path.isdir('gitian-builder'):
        subprocess.check_call(['git', 'clone', 'https://github.com/devrandom/gitian-builder.git'])
    if not os.path.isdir('AltmarketsCoin'):
        subprocess.check_call(['git', 'clone', "%s.git" % (args.url)])
    os.chdir('gitian-builder')
    make_image_prog = ['bin/make-base-vm', '--suite', 'trusty', '--arch', 'amd64']
    if args.docker:
        make_image_prog += ['--docker']
    elif not args.kvm:
        make_image_prog += ['--lxc']
    try:
        subprocess.check_call(make_image_prog)
    except:
        pass
    os.chdir(workdir)
    if args.is_bionic and not args.kvm and not args.docker:
        subprocess.check_call(['sudo', 'sed', '-i', 's/lxcbr0/br0/', '/etc/default/lxc-net'])
        print('Reboot is required')
        sys.exit(0)

def build():
    global args, workdir

    os.makedirs('altmarkets-binaries/' + args.version + '/linux_arm', exist_ok=True)
    os.makedirs('altmarkets-binaries/' + args.version + '/linux', exist_ok=True)
    os.makedirs('altmarkets-binaries/' + args.version + '/win', exist_ok=True)
    os.makedirs('altmarkets-binaries/' + args.version + '/mac', exist_ok=True)
    print('\nBuilding Dependencies\n')
    os.chdir('gitian-builder')
    os.makedirs('inputs', exist_ok=True)

    subprocess.check_call(['wget', '-O', 'inputs/osslsigncode-1.7.1.tar.gz', 'http://downloads.sourceforge.net/project/osslsigncode/osslsigncode/osslsigncode-1.7.1.tar.gz'])
    subprocess.check_call(['wget', '-O', 'inputs/osslsigncode-Backports-to-1.7.1.patch', 'https://bitcoincore.org/cfields/osslsigncode-Backports-to-1.7.1.patch'])
    subprocess.check_call(["echo 'f9a8cdb38b9c309326764ebc937cba1523a3a751a7ab05df3ecc99d18ae466c9 inputs/osslsigncode-1.7.1.tar.gz' | sha256sum -c"], shell=True)
    subprocess.check_call(["echo 'a8c4e9cafba922f89de0df1f2152e7be286aba73f78505169bc351a7938dd911 inputs/osslsigncode-Backports-to-1.7.1.patch' | sha256sum -c"], shell=True)
    subprocess.check_call(['make', '-C', '../AltmarketsCoin/depends', 'download', 'SOURCES_PATH=' + os.getcwd() + '/cache/common'])

    if args.linux:
        print('\nCompiling ' + args.version + ' Linux (ARM)')
        subprocess.check_call(['bin/gbuild', '-j', args.jobs, '-m', args.memory, '--commit', 'AltmarketsCoin='+args.commit, '--url', 'AltmarketsCoin='+args.url, '../AltmarketsCoin/contrib/gitian-descriptors/gitian-arm.yml'])
        subprocess.check_call(['bin/gsign', '-p', args.sign_prog, '--signer', args.signer, '--release', args.version+'-linux', '--destination', '../gitian.sigs.altmarkets/', '../AltmarketsCoin/contrib/gitian-descriptors/gitian-arm.yml'])
        subprocess.check_call('mv build/out/altmarkets-*.tar.gz build/out/src/altmarkets-*.tar.gz ../altmarkets-binaries/'+args.version + '/linux_arm', shell=True)
        try:
            subprocess.check_call('mv var/install.log var/install_linux_arm.log', shell=True)
            subprocess.check_call('mv var/build.log var/build_linux_arm.log', shell=True)
        except:
            pass
        print('\nCompiling ' + args.version + ' Linux')
        subprocess.check_call(['bin/gbuild', '-j', args.jobs, '-m', args.memory, '--commit', 'AltmarketsCoin='+args.commit, '--url', 'AltmarketsCoin='+args.url, '../AltmarketsCoin/contrib/gitian-descriptors/gitian-linux.yml'])
        subprocess.check_call(['bin/gsign', '-p', args.sign_prog, '--signer', args.signer, '--release', args.version+'-linux', '--destination', '../gitian.sigs.altmarkets/', '../AltmarketsCoin/contrib/gitian-descriptors/gitian-linux.yml'])
        subprocess.check_call('mv build/out/altmarkets-*.tar.gz build/out/src/altmarkets-*.tar.gz ../altmarkets-binaries/'+args.version + '/linux', shell=True)
        try:
            subprocess.check_call('mv var/install.log var/install_linux.log', shell=True)
            subprocess.check_call('mv var/build.log var/build_linux.log', shell=True)
        except:
            pass

    if args.windows:
        print('\nCompiling ' + args.version + ' Windows')
        subprocess.check_call(['bin/gbuild', '-j', args.jobs, '-m', args.memory, '--commit', 'AltmarketsCoin='+args.commit, '--url', 'AltmarketsCoin='+args.url, '../AltmarketsCoin/contrib/gitian-descriptors/gitian-win.yml'])
        subprocess.check_call(['bin/gsign', '-p', args.sign_prog, '--signer', args.signer, '--release', args.version+'-win-unsigned', '--destination', '../gitian.sigs.altmarkets/', '../AltmarketsCoin/contrib/gitian-descriptors/gitian-win.yml'])
        # subprocess.check_call('mv build/out/altmarkets-*-win-unsigned.tar.gz inputs/altmarkets-win-unsigned.tar.gz', shell=True)
        subprocess.check_call('mv build/out/altmarkets-*.zip build/out/Altmarkets-*.exe build/out/src/altmarkets-*.tar.gz ../altmarkets-binaries/'+args.version + '/win', shell=True)
        try:
            subprocess.check_call('mv var/install.log var/install_win.log', shell=True)
            subprocess.check_call('mv var/build.log var/build_win.log', shell=True)
        except:
            pass

    if args.macos:
        print('\nCompiling ' + args.version + ' MacOS')
        subprocess.check_call(['bin/gbuild', '-j', args.jobs, '-m', args.memory, '--commit', 'AltmarketsCoin='+args.commit, '--url', 'AltmarketsCoin='+args.url, '../AltmarketsCoin/contrib/gitian-descriptors/gitian-osx.yml'])
        subprocess.check_call(['bin/gsign', '-p', args.sign_prog, '--signer', args.signer, '--release', args.version+'-osx-unsigned', '--destination', '../gitian.sigs.altmarkets/', '../AltmarketsCoin/contrib/gitian-descriptors/gitian-osx.yml'])
        subprocess.check_call('mv build/out/altmarkets-*-osx-unsigned.tar.gz inputs/altmarkets-osx-unsigned.tar.gz', shell=True)
        subprocess.check_call('mv build/out/altmarkets-*.tar.gz build/out/altmarkets-*.dmg build/out/src/altmarkets-*.tar.gz ../altmarkets-binaries/'+args.version + '/mac', shell=True)
        try:
            subprocess.check_call('mv var/install.log var/install_mac.log', shell=True)
            subprocess.check_call('mv var/build.log var/build_mac.log', shell=True)
        except:
            pass

    os.chdir(workdir)

    if args.commit_files:
        print('\nCommitting '+args.version+' Unsigned Sigs\n')
        os.chdir('gitian.sigs.altmarkets')
        if args.linux:
            subprocess.check_call(['git', 'add', args.version+'-linux/'+args.signer])
        if args.windows:
            subprocess.check_call(['git', 'add', args.version+'-win-unsigned/'+args.signer])
        if args.macos:
            subprocess.check_call(['git', 'add', args.version+'-osx-unsigned/'+args.signer])
        subprocess.check_call(['git', 'commit', '-m', 'Add '+args.version+' unsigned sigs for '+args.signer])
        os.chdir(workdir)

def sign():
    global args, workdir
    os.chdir('gitian-builder')

    if args.windows:
        print('\nSigning ' + args.version + ' Windows')
        subprocess.check_call(['bin/gbuild', '--skip-image', '--upgrade', '--commit', 'signature='+args.commit, '../AltmarketsCoin/contrib/gitian-descriptors/gitian-win-signer.yml'])
        subprocess.check_call(['bin/gsign', '-p', args.sign_prog, '--signer', args.signer, '--release', args.version+'-win-signed', '--destination', '../gitian.sigs.altmarkets/', '../AltmarketsCoin/contrib/gitian-descriptors/gitian-win-signer.yml'])
        try:
            subprocess.check_call('mv var/build.log var/build_sign_win.log', shell=True)
        except:
            pass
        try:
            subprocess.check_call('mv build/out/altmarkets-*win32-setup.exe build/out/altmarkets-*win64-setup.exe ../altmarkets-binaries/'+args.version + '/win', shell=True)
        except Exception as e:
            print(e)
            pass

    if args.macos:
        print('\nSigning ' + args.version + ' MacOS')
        subprocess.check_call(['bin/gbuild', '--skip-image', '--upgrade', '--commit', 'signature='+args.commit, '../AltmarketsCoin/contrib/gitian-descriptors/gitian-osx-signer.yml'])
        subprocess.check_call(['bin/gsign', '-p', args.sign_prog, '--signer', args.signer, '--release', args.version+'-osx-signed', '--destination', '../gitian.sigs.altmarkets/', '../AltmarketsCoin/contrib/gitian-descriptors/gitian-osx-signer.yml'])
        try:
            subprocess.check_call('mv var/build.log var/build_sign_mac.log', shell=True)
        except:
            pass
        try:
            subprocess.check_call('mv build/out/altmarkets-osx-signed.dmg ../altmarkets-binaries/' + args.version + '/mac' + '/altmarkets-'+args.version+'-osx.dmg', shell=True)
        except Exception as e:
            print(e)
            pass

    os.chdir(workdir)

    if args.commit_files:
        print('\nCommitting '+args.version+' Signed Sigs\n')
        os.chdir('gitian.sigs.altmarkets')
        if args.windows:
            subprocess.check_call(['git', 'add', args.version+'-win-signed/'+args.signer])
        if args.macos:
            subprocess.check_call(['git', 'add', args.version+'-osx-signed/'+args.signer])
        try:
            subprocess.check_call(['git', 'commit', '-a', '-m', 'Add '+args.version+' signed binary sigs for '+args.signer])
        except Exception as e:
            print(e)
            pass
        os.chdir(workdir)

def make_shasums():
    global args, workdir
    print('\nMaking SHA256SUMs for ' + args.version)
    os.chdir('altmarkets-binaries/'+args.version)
    move_dirs = [
        'mv linux/altmarkets-*.tar.gz ./',
        'mv linux_arm/altmarkets-*-aarch64-linux-gnu.tar.gz linux_arm/altmarkets-*-arm-linux-gnueabihf.tar.gz ./',
        'mv mac/altmarkets-*.dmg mac/altmarkets-*osx64.tar.gz ./',
        'mv win/Altmarkets-*setup.exe win/altmarkets-*.zip ./'
    ]
    for move_dir in move_dirs:
        try:
            subprocess.check_call(move_dir, shell=True)
        except Exception as e:
            pass
    
    try:
        subprocess.check_call('sha256sum * > SHA256SUMS', shell=True)
    except Exception as e:
        pass
    with open("SHA256SUMS", "r") as sum_file:
        lines = sum_file.readlines()
    new_lines = []
    for line in lines:
        if 'debug' not in line and 'unsigned' not in line and 'SHA256SUMS' not in line and 'shasum:' not in line and 'a directory' not in line:
            new_lines.append(line);
    with open("SHA256SUMS.new", "w") as sum_file:
        for line in new_lines:
            sum_file.write(line)
    subprocess.check_call('mv SHA256SUMS SHA256SUMS.full', shell=True)
    subprocess.check_call('mv SHA256SUMS.new SHA256SUMS', shell=True)
    subprocess.check_call(['gpg --digest-algo sha256 --clearsign SHA256SUMS'], shell=True)

def verify():
    global args, workdir
    rc = 0
    os.chdir('gitian-builder')

    print('\nVerifying v'+args.version+' Linux\n')
    if subprocess.call(['bin/gverify', '-v', '-d', '../gitian.sigs.altmarkets/', '-r', args.version+'-linux', '../AltmarketsCoin/contrib/gitian-descriptors/gitian-linux.yml']):
        print('Verifying v'+args.version+' Linux FAILED\n')
        rc = 1

    print('\nVerifying v'+args.version+' Windows\n')
    if subprocess.call(['bin/gverify', '-v', '-d', '../gitian.sigs.altmarkets/', '-r', args.version+'-win-unsigned', '../AltmarketsCoin/contrib/gitian-descriptors/gitian-win.yml']):
        print('Verifying v'+args.version+' Windows FAILED\n')
        rc = 1

    print('\nVerifying v'+args.version+' MacOS\n')
    if subprocess.call(['bin/gverify', '-v', '-d', '../gitian.sigs.altmarkets/', '-r', args.version+'-osx-unsigned', '../AltmarketsCoin/contrib/gitian-descriptors/gitian-osx.yml']):
        print('Verifying v'+args.version+' MacOS FAILED\n')
        rc = 1

    print('\nVerifying v'+args.version+' Signed Windows\n')
    if subprocess.call(['bin/gverify', '-v', '-d', '../gitian.sigs.altmarkets/', '-r', args.version+'-win-signed', '../AltmarketsCoin/contrib/gitian-descriptors/gitian-win-signer.yml']):
        print('Verifying v'+args.version+' Signed Windows FAILED\n')
        rc = 1

    print('\nVerifying v'+args.version+' Signed MacOS\n')
    if subprocess.call(['bin/gverify', '-v', '-d', '../gitian.sigs.altmarkets/', '-r', args.version+'-osx-signed', '../AltmarketsCoin/contrib/gitian-descriptors/gitian-osx-signer.yml']):
        print('Verifying v'+args.version+' Signed MacOS FAILED\n')
        rc = 1

    os.chdir(workdir)
    return rc

def main():
    global args, workdir

    parser = argparse.ArgumentParser(description='Script for running full Gitian builds.')
    parser.add_argument('-c', '--commit', action='store_true', dest='commit', help='Indicate that the version argument is for a commit or branch')
    parser.add_argument('-p', '--pull', action='store_true', dest='pull', help='Indicate that the version argument is the number of a github repository pull request')
    parser.add_argument('-u', '--url', dest='url', default='https://github.com/altmarkets/AltmarketsCoin', help='Specify the URL of the repository. Default is %(default)s')
    parser.add_argument('-v', '--verify', action='store_true', dest='verify', help='Verify the Gitian build')
    parser.add_argument('-b', '--build', action='store_true', dest='build', help='Do a Gitian build')
    parser.add_argument('-s', '--sign', action='store_true', dest='sign', help='Make signed binaries for Windows and MacOS')
    parser.add_argument('-B', '--buildsign', action='store_true', dest='buildsign', help='Build both signed and unsigned binaries')
    parser.add_argument('-o', '--os', dest='os', default='lwm', help='Specify which Operating Systems the build is for. Default is %(default)s. l for Linux, w for Windows, m for MacOS')
    parser.add_argument('-j', '--jobs', dest='jobs', default='2', help='Number of processes to use. Default %(default)s')
    parser.add_argument('-m', '--memory', dest='memory', default='2000', help='Memory to allocate in MiB. Default %(default)s')
    parser.add_argument('-k', '--kvm', action='store_true', dest='kvm', help='Use KVM instead of LXC')
    parser.add_argument('-W', '--wipe-cache', action='store_true', dest='wipe_cache', help='Wipe all cached files.')
    parser.add_argument('--make-shasums', action='store_true', dest='make_shasums', help='Make SHA256 SUMs.')
    parser.add_argument('--install-vmbuilder', action='store_true', dest='install_vmbuilder', help='Install VM Builder.')
    parser.add_argument('-d', '--docker', action='store_true', dest='docker', help='Use Docker instead of LXC')
    parser.add_argument('-S', '--setup', action='store_true', dest='setup', help='Set up the Gitian building environment. Only works on Debian-based systems (Ubuntu, Debian)')
    parser.add_argument('-D', '--detach-sign', action='store_true', dest='detach_sign', help='Create the assert file for detached signing. Will not commit anything.')
    parser.add_argument('-n', '--no-commit', action='store_false', dest='commit_files', help='Do not commit anything to git')
    parser.add_argument('signer', nargs='?', help='GPG signer to sign each build assert file')
    parser.add_argument('version', nargs='?', help='Version number, commit, or branch to build. If building a commit or branch, the -c option must be specified')

    args = parser.parse_args()
    workdir = os.getcwd()

    args.is_bionic = b'bionic' in subprocess.check_output(['lsb_release', '-cs'])

    if args.kvm and args.docker:
        raise Exception('Error: cannot have both kvm and docker')

    # Ensure no more than one environment variable for gitian-builder (USE_LXC, USE_VBOX, USE_DOCKER) is set as they
    # can interfere (e.g., USE_LXC being set shadows USE_DOCKER; for details see gitian-builder/libexec/make-clean-vm).
    os.environ['USE_LXC'] = ''
    os.environ['USE_VBOX'] = ''
    os.environ['USE_DOCKER'] = ''
    if args.docker:
        os.environ['USE_DOCKER'] = '1'
    elif not args.kvm:
        os.environ['USE_LXC'] = '1'
        if 'GITIAN_HOST_IP' not in os.environ.keys():
            os.environ['GITIAN_HOST_IP'] = '10.0.3.2'
        if 'LXC_GUEST_IP' not in os.environ.keys():
            os.environ['LXC_GUEST_IP'] = '10.0.3.5'

    if args.setup:
        setup()

    if args.make_shasums:
        make_shasums()

    if args.install_vmbuilder:
        InstallVMBuilder()

    if args.buildsign:
        args.build = True
        args.sign = True

    if not args.build and not args.sign and not args.verify:
        sys.exit(0)

    args.linux = 'l' in args.os
    args.windows = 'w' in args.os
    args.macos = 'm' in args.os

    # Disable for MacOS if no SDK found
    if args.macos and not os.path.isfile('gitian-builder/inputs/MacOSX10.11.sdk.tar.gz'):
        print('Cannot build for MacOS, SDK does not exist. Will build for other OSes')
        args.macos = False

    args.sign_prog = 'true' if args.detach_sign else 'gpg --detach-sign'

    script_name = os.path.basename(sys.argv[0])
    if not args.signer:
        print(script_name+': Missing signer')
        print('Try '+script_name+' --help for more information')
        sys.exit(1)
    if not args.version:
        print(script_name+': Missing version')
        print('Try '+script_name+' --help for more information')
        sys.exit(1)

    # Add leading 'v' for tags
    if args.commit and args.pull:
        raise Exception('Cannot have both commit and pull')
    args.commit = ('' if args.commit else 'v') + args.version

    os.chdir('AltmarketsCoin')
    if args.pull:
        subprocess.check_call(['git', 'fetch', args.url, 'refs/pull/'+args.version+'/merge'])
        os.chdir('../gitian-builder/inputs/AltmarketsCoin')
        subprocess.check_call(['git', 'fetch', args.url, 'refs/pull/'+args.version+'/merge'])
        args.commit = subprocess.check_output(['git', 'show', '-s', '--format=%H', 'FETCH_HEAD'], universal_newlines=True, encoding='utf8').strip()
        args.version = 'pull-' + args.version
    print(args.commit)
    subprocess.check_call(['git', 'fetch'])
    subprocess.check_call(['git', 'checkout', args.commit])
    os.chdir(workdir)

    os.chdir('gitian-builder')
    subprocess.check_call(['git', 'pull'])
    os.chdir(workdir)

    if args.build:
        build()

    if args.sign:
        sign()

    if args.verify:
        os.chdir('gitian.sigs.altmarkets')
        subprocess.check_call(['git', 'pull'])
        os.chdir(workdir)
        sys.exit(verify())

if __name__ == '__main__':
    main()
