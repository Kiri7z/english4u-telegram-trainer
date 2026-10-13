"""Build and test a working copy on a server without touching the live application."""

import argparse
import pathlib
import re
import shlex
import subprocess
import tarfile
import tempfile
import uuid


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ssh-target', required=True, help='An SSH alias or user@host')
    args = parser.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9_.@-]+', args.ssh_target) or args.ssh_target.startswith('-'):
        parser.error('Use an SSH alias or user@host without shell characters')
    root = pathlib.Path(__file__).resolve().parents[1]
    names = subprocess.check_output(
        ['git', '-C', str(root), 'ls-files', '--cached', '--others', '--exclude-standard', '-z']
    ).decode().split('\0')
    identifier = uuid.uuid4().hex[:12]
    tags = [f'english4u-check-web:{identifier}', f'english4u-check-bot:{identifier}']

    def remote(command, **kwargs):
        return subprocess.run(['ssh', '-o', 'BatchMode=yes', '--', args.ssh_target,
                               shlex.join(command)], check=True, **kwargs)

    stage = remote(['mktemp', '-d', '/tmp/english4u-check.XXXXXXXX'],
                   capture_output=True, text=True).stdout.strip()
    if not re.fullmatch(r'/tmp/english4u-check\.[A-Za-z0-9]+', stage):
        raise RuntimeError('Unexpected staging directory')
    try:
        with tempfile.TemporaryDirectory(prefix='english4u-check-') as temporary:
            archive_path = pathlib.Path(temporary) / 'source.tar.gz'
            with tarfile.open(archive_path, 'w:gz') as archive:
                for name in filter(None, names):
                    path = pathlib.PurePosixPath(name)
                    if any(part in ('postgres', 'postgress', 'backups', 'secrets', '.git')
                           for part in path.parts) or (path.name.startswith('.env')
                                                     and path.name != '.env.example'):
                        raise RuntimeError(f'Refusing to upload a private file: {name}')
                    source = root / name
                    if source.is_symlink():
                        raise RuntimeError(f'Refusing to upload a symlink: {name}')
                    archive.add(source, arcname=name, recursive=False)
            subprocess.run(['scp', '-q', '--', str(archive_path),
                            f'{args.ssh_target}:{stage}/source.tar.gz'], check=True)
        remote(['tar', '-xzf', stage + '/source.tar.gz', '-C', stage])
        for component, tag in zip(('my_flask_app', 'telegram_bot'), tags):
            remote(['docker', 'build', '--tag', tag, '--file',
                    stage + '/' + component + '/dockerfile', stage])
        for tag, pattern in ((tags[1], 'test_bot.py'), (tags[0], 'test_web_security.py'),
                             (tags[0], 'test_rate_limit.py')):
            remote(['docker', 'run', '--rm', '--network', 'none',
                    '--env', 'DB_USER=test_user', '--env', 'DB_PASSWORD=test-only-password',
                    '--env', 'DB_NAME=test_db', '--env', 'FLASK_SECRET_KEY=test-only-flask-secret',
                    '--env', 'TELEGRAM_TOKEN=123456:unit-test-placeholder',
                    '--volume', stage + ':/workspace:ro', '--workdir', '/workspace',
                    '--entrypoint', 'python', tag, '-m', 'unittest', 'discover',
                    '-s', 'tests', '-p', pattern, '-v'])
        print('Server checks passed. The live application has not been changed.')
    finally:
        for tag in tags:
            subprocess.run(['ssh', '-o', 'BatchMode=yes', '--', args.ssh_target,
                            shlex.join(['docker', 'image', 'rm', tag])], check=False,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        remote(['rm', '-rf', '--', stage])


if __name__ == '__main__':
    main()
