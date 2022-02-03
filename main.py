#!/usr/bin/python3

# TODO: Comments in yaml
#       SSH Send/Overwrite


import sys,os,time
import logging,csv
import PySimpleGUI as sg
import pandas as pd
import yaml


class yamlHandler:
    def __init__(self):
        if getattr(sys, 'frozen', False):
            self.src_folder = sys._MEIPASS
        else:
            self.src_folder = os.path.dirname(os.path.abspath(__file__))
        self.src_path = self.src_folder + "\config.yaml"
        self.prim_setup()

    def prim_setup(self):
        try:
            if os.path.exists(self.src_path):
                # Only allow Config changed if program is in frozen state (exe)
                if not getattr(sys, 'frozen', False):
                    os.remove(self.src_path)
                    self.setup()
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
    _input=_target=_yaml=_type=_server=_slot=None
    _filter = ['#']     #append filter options
    _storage = []
    _filedict = {}
    _offset = 0

    def __init__(self,*args):
        for arg in args:
            if 'input' in arg:
                self._input = arg['input']
            if 'target' in arg:
                self._target = arg['target']

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


            # MgntName = "NODENAME"; -> dict Nodename
            # MngtCntrlType = 1;  -> dict DCCT,Subtype
            # PSName = "NODENAME"; -> dict Nodename
            # PsCircuitName = 32443; -> dict Kreisnum

            for config in self._storage:
                dcct = config["DCCT"]
                subtype = config["SUBTYPE"]
                #filename =
                conf_str = ''
                if dcct in self._type.index.values and subtype in self._type.columns.values:
                    conf_str += f'MgntName = "{config["NODENAME"]}";\n'
                    conf_str += f'MgntCntrlType = {self._type.at[dcct,subtype]};\n'
                    conf_str += f'PsName = "{config["NODENAME"]}";\n'
                    conf_str += f'PsCircuitName = {config["KREISNUM"]}\n'
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


    def writearea(self,data : dict):
        key = ''
        try:
            for key in data:

                # create folder struct
                __dir = os.path.dirname(key)
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


def simplegui():
    sg.theme('Reddit')
    layout = []
    layout.append([sg.Text('Input File')])
    layout.append([sg.Input(key = 'input'), sg.FileBrowse(file_types=(('CRATE Config Files', '*.csv'),))])
    layout.append([sg.Text('Export Folder')])
    layout.append([sg.Input(key = 'target'), sg.FolderBrowse()])
    layout.append([[sg.Ok("Create"), sg.Cancel()]])
    window = sg.Window('ConfigParser', layout)
    event,values = window.read()

    if event == sg.WIN_CLOSED or event == 'Cancel':
        window.close()
        sys.exit(1996)
    elif event == 'Create':
        return values


def init_logging():
    log_format = f"%(asctime)s [%(processName)s] [%(name)s] [%(levelname)s] %(message)s"
    log_level = logging.DEBUG
    if getattr(sys, 'frozen', False):
        folder = sys._MEIPASS
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
        rd.create()

    except:
        logging.error(f'Unable to launch Program')
        logging.error(f'{sys.exc_info()[1]}')
        logging.error(f'Error on line {sys.exc_info()[-1].tb_lineno}')

    finally:
        logging.info(f'Program finished')


if __name__ == '__main__':
    main()


