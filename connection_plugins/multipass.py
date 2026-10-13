from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

from ansible.plugins.connection import ConnectionBase
from ansible.errors import AnsibleError
from ansible.module_utils.common.text.converters import to_bytes, to_text
import subprocess
import shutil
import os
import tempfile

DOCUMENTATION = '''
    connection: multipass
    short_description: Execute commands via multipass exec
    description:
        - Run commands on Multipass VMs using C(multipass exec) instead of SSH.
        - File transfers use C(multipass transfer).
        - Requires Multipass to be installed on the Ansible controller.
    author: Yann Ghistelinck
    options:
      remote_addr:
        description:
            - The Multipass VM instance name.
        vars:
            - name: ansible_host
      become_user:
        description: User to become on the remote system.
        default: root
'''


class Connection(ConnectionBase):
    """Multipass exec based connection plugin."""

    transport = 'multipass'
    has_pipelining = True

    def __init__(self, *args, **kwargs):
        super(Connection, self).__init__(*args, **kwargs)
        self.instance_name = None

    def _connect(self):
        """Connect to the Multipass instance."""
        super(Connection, self)._connect()
        self.instance_name = self.get_option('remote_addr') or self._play_context.remote_addr
        if not self.instance_name:
            raise AnsibleError("No Multipass instance name provided. Set ansible_host to the VM name.")
        self._connected = True
        return self

    def exec_command(self, cmd, in_data=None, sudoable=True):
        """Execute a command on the Multipass instance."""
        super(Connection, self).exec_command(cmd, in_data=in_data, sudoable=sudoable)

        multipass_cmd = ['multipass', 'exec', self.instance_name, '--']

        if sudoable and self._play_context.become:
            become_user = self._play_context.become_user or 'root'
            if self._play_context.become_method == 'sudo':
                cmd = f"sudo -u {become_user} sh -c {self._shell.quote(cmd)}"

        multipass_cmd.extend(['sh', '-c', cmd])

        try:
            process = subprocess.Popen(
                multipass_cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            stdout, stderr = process.communicate(input=to_bytes(in_data) if in_data else None)
            return (process.returncode, to_text(stdout), to_text(stderr))
        except FileNotFoundError:
            raise AnsibleError(
                "multipass command not found. Ensure Multipass is installed and available in PATH."
            )
        except Exception as e:
            raise AnsibleError(f"Failed to execute command on '{self.instance_name}': {e}")

    def put_file(self, in_path, out_path):
        """Transfer a file to the Multipass instance."""
        super(Connection, self).put_file(in_path, out_path)

        tmp_local = None
        try:
            # On Linux, the Multipass daemon uses SFTP internally for transfers
            # and runs as a different user, so it cannot read files from the
            # Ansible temp directory (~/.ansible/tmp/). Copy to /tmp/ first.
            fd, tmp_local = tempfile.mkstemp(prefix='ansible-mp-put-', dir='/tmp')
            os.close(fd)
            shutil.copy2(in_path, tmp_local)
            os.chmod(tmp_local, 0o644)

            # multipass transfer cannot write directly to privileged paths,
            # so we transfer to a temp location then move it into place.
            tmp_dest = f"/tmp/ansible-tmp-{os.path.basename(out_path)}"

            subprocess.check_call(
                ['multipass', 'transfer', tmp_local, f"{self.instance_name}:{tmp_dest}"]
            )
            subprocess.check_call(
                ['multipass', 'exec', self.instance_name, '--', 'sudo', 'mv', tmp_dest, out_path]
            )
        except FileNotFoundError:
            raise AnsibleError(
                "multipass command not found. Ensure Multipass is installed and available in PATH."
            )
        except subprocess.CalledProcessError as e:
            raise AnsibleError(f"Failed to transfer file to '{self.instance_name}:{out_path}': {e}")
        finally:
            if tmp_local and os.path.exists(tmp_local):
                os.unlink(tmp_local)

    def fetch_file(self, in_path, out_path):
        """Fetch a file from the Multipass instance."""
        super(Connection, self).fetch_file(in_path, out_path)

        tmp_local = None
        try:
            # For privileged files, copy to a temp location on the VM first.
            tmp_src = f"/tmp/ansible-fetch-{os.path.basename(in_path)}"

            subprocess.check_call(
                ['multipass', 'exec', self.instance_name, '--',
                 'sudo', 'cp', in_path, tmp_src]
            )
            subprocess.check_call(
                ['multipass', 'exec', self.instance_name, '--',
                 'sudo', 'chmod', '644', tmp_src]
            )

            # On Linux, the Multipass daemon uses SFTP internally and cannot
            # write to the Ansible temp directory. Transfer to /tmp/ first.
            fd, tmp_local = tempfile.mkstemp(prefix='ansible-mp-fetch-', dir='/tmp')
            os.close(fd)

            subprocess.check_call(
                ['multipass', 'transfer', f"{self.instance_name}:{tmp_src}", tmp_local]
            )
            subprocess.check_call(
                ['multipass', 'exec', self.instance_name, '--',
                 'sudo', 'rm', '-f', tmp_src]
            )
            shutil.copy2(tmp_local, out_path)
        except FileNotFoundError:
            raise AnsibleError(
                "multipass command not found. Ensure Multipass is installed and available in PATH."
            )
        except subprocess.CalledProcessError as e:
            raise AnsibleError(f"Failed to fetch file from '{self.instance_name}:{in_path}': {e}")
        finally:
            if tmp_local and os.path.exists(tmp_local):
                os.unlink(tmp_local)

    def close(self):
        """Close the connection."""
        super(Connection, self).close()
        self._connected = False
