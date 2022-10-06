#!/usr/bin/python3

# TODO: Comments in yaml
#       SSH Send/Overwrite


import sys, os, time
import logging, csv
import PySimpleGUI as sg
import pandas as pd
import yaml
import paramiko
from stat import S_ISDIR


class yamlHandler:
    def __init__(self):
        if getattr(sys, 'frozen', False):
            self.src_folder = os.path.dirname(sys.executable)
        else:
            self.src_folder = os.path.dirname(os.path.abspath(__file__))
        self.src_path = self.src_folder + "\config.yaml"
        self.prim_setup()

    def prim_setup(self):
        try:
            if os.path.exists(self.src_path):
                return
                # Only allow Config changed if program is in frozen state (exe)
                #if not getattr(sys, 'frozen', False):
                    #os.remove(self.src_path)
                    #self.setup()
            else:
                self.setup()

        except:
            logging.error(f'Unable to launch Program')
            logging.error(f'{sys.exc_info()[1]}')
            logging.error(f'Error on line {sys.exc_info()[-1].tb_lineno}')


    def setup(self):
        self.data = {
            # Type Lookup Table
            'type' : [[1,0,0,0],
                     [2,0,0,0],
                     [3,0,0,0],
                     [4,5,7,0],
                     [0,6,0,0],
                     [0,0,0,8],
                     [0,0,0,9],
                     [0,0,0,10]],
            'type_name' : ['COPC-1','COPC-2','COPC-4','COPC-6'],
            'type_DCCT' : ['3.5','2','0.35','10','13.5','20','15','30'],
            # Server Lookup Table
            'server': [('flashcpumag-b','flashcpumag-c','flashcpumag-d'),
                       ('flashcpumag-e','flashcpumag-f','flashcpumag-g')],
            'server_node' : ['1','2','3'],
            'server_line' : ['27','28']
            # Add SUBADDR?
        }
        with open(self.src_path,'w',encoding='utf8') as f:
            yaml.safe_dump(self.data, f)
        f.close()


    def read(self, key):
        self.key = key
        with open(self.src_path, 'r') as f:
            self.ret_val = yaml.safe_load(f)
            if self.ret_val is None:
                return False
            else:
                try:
                    return (self.ret_val[key])
                except KeyError:
                    logging.error("Broken Key in Yaml File. Delete " + self.src_path + " and retry.")
                    exit()


    def add(self,key,value):
        try:
            assert key
            self.key=key
            self.value=value
            with open(self.src_path,'r') as f:
                yaml_cont=yaml.safe_load(f) or {}
            yaml_cont[self.key]=self.value
            with open(self.src_path,'w') as f:
                yaml.dump(yaml_cont,f)
        except:
            logging.info(f"unable to add {key} to file")
            logging.error(f'{sys.exc_info()[1]}')
            logging.error(f'Error on line {sys.exc_info()[-1].tb_lineno}')



class Reader:
    _input=_target=_yaml=_type=_server=_slot=_ssh=_sftp=None
    _filter = ['#']     #append filter options
    _storage = []
    _filedict = {}
    _offset = 0
    _state = 'local'

    def __init__(self, *args):
        for arg in args:
            if 'input' in arg:
                self._input = arg['input']
            if 'target' in arg:
                self._target = arg['target']
            if 'state' in arg:
                self._state = arg['state']
            if 'ssh' in arg:
                self._ssh:paramiko.SSHClient = arg['ssh']
            if 'sftp' in arg:
                self._sftp:paramiko.SFTPClient = arg['sftp']


        self._yaml = yamlHandler()
        self.create_df()


    def create_df(self):
        try:
            # Type Dataframe
            self.data = self._yaml.read('type')
            self.colname = self._yaml.read('type_name')
            self.index = self._yaml.read('type_DCCT')
            self._type = pd.DataFrame(self.data,columns = self.colname,index = self.index)

            # Server Dataframe
            self.data = self._yaml.read('server')
            self.colname = self._yaml.read('server_node')
            self.index = self._yaml.read('server_line')
            self._server= pd.DataFrame(self.data, columns=self.colname, index=self.index)

            # Slot Func
            self._slot = lambda x: int((int(x) -32)/16)

        except:
            logging.error(f'Creation of Lookup matrix failed.')
            logging.error(f'{sys.exc_info()[1]}')
            logging.error(f'Error on line {sys.exc_info()[-1].tb_lineno}')



    def create(self):
        try:
            if not self._input or not self._target:
                raise KeyError("Input file or target folder are missing")

            # Filter self._filter
            with open(self._input) as csvfile:
                while any(match in csvfile.readline() for match in self._filter):
                    self._offset = csvfile.tell()
                csvfile.seek(self._offset)
                self.reader = csv.DictReader(csvfile)

                for csvdict in self.reader:
                    if all(match not in value for value in csvdict.values() for match in self._filter):
                        self._storage.append({key.replace(' ','') : value.replace(' ','') for key,value in csvdict.items()})

            ########### General Struct ##############
            # MgntName = "NODENAME"; -> dict Nodename
            # MngtCntrlType = 1;  -> dict DCCT,Subtype
            # PSName = "NODENAME"; -> dict Nodename
            # PsCircuitName = 32443; -> dict Kreisnum
            #########################################

            for config in self._storage:
                dcct = config["DCCT"]
                subtype = config["PSNAME"]
                conf_str = ''
                if dcct in self._type.index.values and subtype in self._type.columns.values:
                    conf_str += f'MgntName = "{config["NODENAME"]}";\n'
                    conf_str += f'MgntCntrlType = {self._type.at[dcct,subtype]};\n'
                    conf_str += f'PsName = "{config["NODENAME"]}";\n'
                    conf_str += f'PsCircuitNumber = {config["KREISNUM"]};\n'
                    folder = os.path.join(self._target,self._server.at[config["LINENUM"],config["NODEID"]])
                    filename = os.path.join(folder,f'SLOT{self._slot(config["SUBADDR"])}.cfg')
                    self._filedict[filename] = conf_str

            if len(self._filedict) > 0:
                self.writearea(self._filedict)
            else:
                logging.error(f'No valid Config Data in {self._input}')

        except KeyError:
            logging.error(f'Invalid key used for lookup. Make sure {sys.exc_info()[1]} is in Config File.')
            logging.error(f'Error on line {sys.exc_info()[-1].tb_lineno}')

        except:
            logging.error(f'error creating internal lookup matrix. please check if the config values are valid')
            logging.error(f'{sys.exc_info()[1]}')
            logging.error(f'Error on line {sys.exc_info()[-1].tb_lineno}')

        finally:
            return {self._target: len(self._filedict)}


    def writearea(self,data : dict):
        key = ''
        try:
            for key in data:
                # create folder struct
                __dir = os.path.dirname(key)
                if self._state == 'ssh':
                    ##########
                    # SSH Path
                    ##########
                    # Create folder if it doesn't already exist
                    try:
                        self._sftp.stat(__dir)
                    except:
                        self._sftp.mkdir(__dir)

                    # Write file if it doesn't already exist
                    try:
                        with self._sftp.open(key,'wx') as f:
                            f.write(data[key])
                    except:
                        logging.error(f'Error file {key} already exists or is permission is insufficient.')

                else:
                    #################
                    # local File Path
                    #################
                    # Create folder if it doesn't already exist
                    if not os.path.exists(__dir):
                        os.makedirs(__dir)

                    # Write file if it doesn't already exist
                    if os.path.isfile(key):
                        logging.error(f'file {key} already exists ')
                    else:
                        with open(key, 'w') as file:
                            file.write(data[key])


        except:
            logging.error(f'Error writing file {key} to target')
            logging.error(f'{sys.exc_info()[1]}')
            logging.error(f'Error on line {sys.exc_info()[-1].tb_lineno}')


        finally:
            if self._sftp is not None:
                self._sftp.close()

def errormsg():
    layout = [[sg.Text('Invalid Connection Parameters')],
              [sg.Button('OK')]]
    window = sg.Window('Error', layout)
    events, values = window.read()
    if events == sg.WIN_CLOSED or events == 'OK':
        window.close()
        return

def compl_message(dict_result):
    for key in dict_result:
        path = key
        length = dict_result[key]
        layout = [[sg.Text(f'{length} files successfully written to {path}.')],
                  [sg.Button('OK')]]
        window = sg.Window('Finished', layout)
        events, values = window.read(timeout=10000)
        window.close()
    return


def sshgui():
    try:
        sg.theme('Reddit')
        _server = _port = _user = _pw = None
        _connected = False
        folder_icon = b'iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/' \
                      b'9hAAAACXBIWXMAAAsSAAALEgHS3X78AAABnUlEQVQ4y8' \
                      b'WSv2rUQRSFv7vZgJFFsQg2EkWb4AvEJ8hqKVilSmFn3iNv' \
                      b'IAp21oIW9haihBRKiqwElMVsIJjNrprsOr/5dyzml3UhEQIW' \
                      b'Hhjmcpn7zblw4B9lJ8Xag9mlmQb3AJzX3tOX8Tngzg349q7t5xcfz' \
                      b'pKGhOFHnjx+9qLTzW8wsmFTL2Gzk7Y2O/k9kCbtwUZbV+Zvo8Md3PALrj' \
                      b'oiqsKSR9ljpAJpwOsNtlfXfRvoNU8Arr/NsVo0ry5z4dZN5hoGqEzYDChB' \
                      b'OoKwS/vSq0XW3y5NAI/uN1cvLqzQur4MCpBGEEd1PQDfQ74HYR+LfeQO' \
                      b'AOYAmgAmbly+dgfid5CHPIKqC74L8RDyGPIYy7+QQjFWa7ICsQ8SpB/IfcJ' \
                      b'SDVMAJUwJkYDMNOEPIBxA/gnuMyYPijXAI3lMse7FGnIKsIuqrxgRSeXOoYZUC' \
                      b'I8pIKW/OHA7kD2YYcpAKgM5ABXk4qSsdJaDOMCsgTIYAlL5TQFTyUIZDmev0N/bnw' \
                      b'qnylEBQS45UKnHx/lUlFvA3fo+jwR8ALb47/oNma38cuqiJ9AAAAAASUVORK5CYII='
        warning = 'Attention this Client has an Autoadd Policy for SSH Server Keys!'

        treedata = sg.TreeData()
        treedata.Insert('', '.', '.', [], icon=folder_icon)
        tree = sg.Tree(treedata, headings=[], col0_width=80, num_rows=10, show_expanded=True, enable_events=True, key='-TREE-')

        layout = []
        layout.append([sg.Text('Server:'),sg.Input(key='server')])
        layout.append([sg.Text('Port:'), sg.Input(key='port',default_text="22")])
        layout.append([sg.Text('User:'), sg.Input(key='user')])
        layout.append([sg.Text('Password:'), sg.Input(key='password', password_char='*')])
        layout.append([sg.Button('Connect'), sg.Cancel()])
        layout.append([tree])
        layout.append([sg.Button('Select Folder',key='select'),sg.Text(warning,text_color='red')])
        window = sg.Window('Remote Connection', layout)
        while True:
            event, values = window.read()
            if not ('<Double-1>' in tree.user_bind_dict.keys()):
                tree.bind('<Double-1>', "DOUBLE")
            if event == sg.WIN_CLOSED or event == 'Cancel':
                break
            elif event == 'Connect':
                _server = values['server'].strip()
                _port = int(values['port'])
                _user = values['user']
                _pw = values['password']
                # build a transport
                ssh = paramiko.SSHClient()
                ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                # Connect
                try:
                    ssh.connect(_server, _port, _user, _pw, timeout=2.0)
                    # get transport layer
                    transport = ssh.get_transport()
                    # build client
                    sftp = paramiko.SFTPClient.from_transport(transport)
                    list_dirs = [el.filename for el in sftp.listdir_attr('.') if S_ISDIR(el.st_mode)]
                    for dir in list_dirs:
                        parent_key = treedata.tree_dict['.'].key
                        key = os.path.join(parent_key, dir)
                        treedata.insert(parent_key, key, str(dir), [], folder_icon)
                    tree.update(values=treedata)
                    _connected = True
                except:
                    errormsg()

            elif event == '-TREE-DOUBLE' and _connected and len(values['-TREE-']) > 0 :
                selected_key = values['-TREE-'][0]
                list_dirs = [el.filename for el in sftp.listdir_attr(selected_key) if S_ISDIR(el.st_mode)]
                treedata.tree_dict[selected_key].children.clear()
                for dir in list_dirs:
                    key = os.path.join(selected_key, dir)
                    treedata.insert(selected_key, key, str(dir), [], folder_icon)
                tree.update(values=treedata)

            elif event == 'select' and _connected and len(values['-TREE-']) > 0:
                selected_key = values['-TREE-'][0]
                window.close()
                return {'ssh':ssh, 'sftp':sftp, 'key':selected_key}

        window.close()


    except paramiko.SSHException:
        errormsg()


    except:
        logging.error(f'SSH GUI produced an error.')
        logging.error(f'{sys.exc_info()[1]}')
        logging.error(f'Error on line {sys.exc_info()[-1].tb_lineno}')



def simplegui():
    try:
        sg.theme('Reddit')
        dict_ssh = dict_state = {}
        layout = []
        layout.append([sg.Text('Input File')])
        layout.append([sg.Input(key='input'), sg.FileBrowse(file_types=(('CRATE Config Files', '*.csv'),))])
        layout.append([sg.Input(key='dummy',visible=False, enable_events=True)])
        layout.append([sg.Text('Export Folder')])
        layout.append([sg.Input(key='target'), sg.FolderBrowse(target='dummy', button_text=' Local Folder'),
                       sg.Button(button_text='Remote Folder', key='ssh')])
        layout.append([[sg.Ok("Create"), sg.Cancel()]])
        window = sg.Window('ConfigParser', layout)
        while True:
            event, values = window.read()

            if event == sg.WIN_CLOSED or event == 'Cancel':
                window.close()
                sys.exit('Program aborted manually')
            elif event == 'dummy':
                dict_state['state'] = 'local'
                window['target'].update(value=window['dummy'].get())
            elif event == 'ssh':
                dict_ssh = sshgui()
                dict_state['state'] = 'ssh'
                window['target'].update(value=dict_ssh['key'])
            elif event == 'Create':
                values.update(dict_ssh)
                values.update(dict_state)
                window.close()
                return values
    except:
        logging.error(f'Main GUI produced an error.')
        logging.error(f'{sys.exc_info()[1]}')
        logging.error(f'Error on line {sys.exc_info()[-1].tb_lineno}')


def init_logging():
    log_format = f"%(asctime)s [%(processName)s] [%(name)s] [%(levelname)s] %(message)s"
    log_level = logging.DEBUG
    if getattr(sys, 'frozen', False):
        folder = os.path.dirname(sys.executable)
    else:
        folder = os.path.dirname(os.path.abspath(__file__))
    # noinspection PyArgumentList
    logging.basicConfig(
        format=log_format,
        level=log_level,
        force=True,
        handlers=[
            logging.FileHandler(filename=f'{folder}\\debug.log', mode='w', encoding='utf-8'),
            logging.StreamHandler(sys.stdout)

        ]
    )

def main():
    try:
        init_logging()
        rd = Reader(simplegui())
        compl_message(rd.create())

    except:
        logging.error(f'Unable to launch Program')
        logging.error(f'{sys.exc_info()[1]}')
        logging.error(f'Error on line {sys.exc_info()[-1].tb_lineno}')

    finally:
        logging.info(f'Program finished')


if __name__ == '__main__':
    main()


