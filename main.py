#!/usr/bin/python3

import sys,os,re,time
import logging,csv
import PySimpleGUI as sg
import pandas as pd
import yaml


class yamlHandler:
    def __init__(self):
        self.src_path = os.path.split((os.path.realpath(__file__)))[0] + "\config.yaml"

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
        # Type Dataframe
        self.type = [(1,0,0,0),
                     (2,0,0,0),
                     (3,0,0,0),
                     (4,5,7,0),
                     (0,6,0,0),
                     (0,0,0,8),
                     (0,0,0,9),
                     (0,0,0,10)]
        self.col = ['COPC-1','COPC-2','COPC-4','COPC-6']
        self.index = ['3.5','2','0.35','10','13.5','20','15','30']
        self._type = pd.DataFrame(self.type, columns=self.col, index=self.index)


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
    _input=_target=_type=_server=_slot= None
    _filter = ['#']     #append filter options
    _storage = []

    def __init__(self,*args):
        for arg in args:
            if 'input' in arg:
                self._input = arg['input']
            if 'target' in arg:
                self._target = arg['target']
        self.create_df()

    def create_df(self):
        # Type Dataframe
        self.type = [(1,0,0,0),
                     (2,0,0,0),
                     (3,0,0,0),
                     (4,5,7,0),
                     (0,6,0,0),
                     (0,0,0,8),
                     (0,0,0,9),
                     (0,0,0,10)]
        self.col = ['COPC-1','COPC-2','COPC-4','COPC-6']
        self.index = ['3.5','2','0.35','10','13.5','20','15','30']
        self._type = pd.DataFrame(self.type,columns = self.col,index = self.index)

        # Server Dataframe
        self.server = [('flashcpumag-b','flashcpumag-c','flashcpumag-d'),
                       ('flashcpumag-e','flashcpumag-f','flashcpumag-g')]
        self.col = ['1','2','3']
        self.index = ['27','28']
        self._server = pd.DataFrame(self.server,columns=self.col,index=self.index)

        # Slot Func
        self._slot = lambda x: int((int(x) -32)/16)

    def create(self):
        try:
            if not self._input or not self._target:
                raise KeyError("Input file or target folder are missing")

            # Filter self._filter
            with open(self._input) as csvfile:
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
                    conf_str += f'MngtCntrlType = "{self._type.at[dcct,subtype]}";\n'
                    conf_str += f'PSName = "{config["NODENAME"]}";\n'
                    conf_str += f'PsCircuitName = "{config["KREISNUM"]}"\n'

                    print(f'slot {self._slot(config["SUBADDR"])}')
                    print(f'server {self._server.at[config["LINENUM"],config["NODEID"]]}')


        except:
            logging.error(f'Unable to launch Program')
            logging.error(f'{sys.exc_info()[1]}')
            logging.error(f'Error on line {sys.exc_info()[-1].tb_lineno}')



def gui_selection():
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
    # noinspection PyArgumentList
    logging.basicConfig(
        format=log_format,
        level=log_level,
        force=True,
        handlers=[
            logging.FileHandler(filename=f'{os.path.dirname(__file__)}\\debug.log', mode='w', encoding='utf-8'),
            logging.StreamHandler(sys.stdout)

        ]
    )

def main():
    try:
        init_logging()
        rd = Reader(gui_selection())
        rd.create()

    except:
        logging.error(f'Unable to launch Program')
        logging.error(f'{sys.exc_info()[1]}')
        logging.error(f'Error on line {sys.exc_info()[-1].tb_lineno}')

    finally:
        logging.info(f'Program finished')


if __name__ == '__main__':
    main()


