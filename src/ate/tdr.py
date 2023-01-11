""" 
The Module 'tdr' short for 'Test Data Record' provides the needed utilities to handle recorded test results
from the generated csv file of the ATE test software.
"""
from __future__ import annotations
__all__ = ("Csv")



import pandas as pd
from pandas import DataFrame
import re
import numpy as np

from ate.pcf import Pcf
from kemx.templates import Record

DATE_COLUMN_NAME = '[TIME] TIMESTAMP / RECORD ID'
SERIAL_COLUMN_NAME = '[CONFIG] UUT SERIAL NUMBER'

class TdrsCsv:

    """ 
    The TdrsCsv (Test Data Records Csv) class describes a csv file containing test records
    that are generated at runtime
    """

    def __init__(self, csv_path:str, test_spec:Pcf.Section) -> None:
        self.csv_path = csv_path
        self.test_spec = test_spec
        self.df:DataFrame = None
        self._update_df()
    
    
    @property
    def records(self) -> list[TestDataRecord]:
        """
        returns records (rows) cointained by the csv file
        """
        return [self.TestDataRecord(self, self.df.iloc[idx]) for idx in self.df.index]

    def _to_datetime(self):
        self.df[DATE_COLUMN_NAME] = pd.to_datetime(self.df[DATE_COLUMN_NAME], format='%Y-%m-%d_%H:%M:%S.%f')
    
    def get_last_record(self) -> TestDataRecord:
        self._update_df()
        return self.TestDataRecord(self, self.df.iloc[self.df[DATE_COLUMN_NAME].argmax()])
    
    def _update_df(self):
        self.df = pd.read_csv(self.csv_path, sep=',')
        self._to_datetime()
    
    class TestDataRecord(Record):
        """
        Describes record (row) of csv file, the record contains all the
        information generated by a finished test sequence
        """

        def __init__(self, csv:TdrsCsv, data:pd.Series) -> None:
            self.csv = csv
            self.data = data
            self.date = data.get(DATE_COLUMN_NAME)
            self.serial = data.get(SERIAL_COLUMN_NAME)
            self.status = None
            self.set_status()

        

        def set_status(self):
            try:
                self.status = True if self.data["[RESULT] TEST P/F STATUS"] == 'PASS' else False
            finally:
                self.data = self.data.drop("[RESULT] TEST P/F STATUS")

        
        def __get_failed_tests(self) -> list[Test]:
            return [test for test in self.tests if "FAIL" in str(test.data)]

        def build_failstring(self):
            failstring:str = ""
            for test in self.__get_failed_tests():

                failstring += '|ftestres=0,{},{},{},{},{},{},{}\n'. \
                    format(
                        test.name,
                        test.meas,
                        test.high_limit,
                        test.low_limit,
                        test.nominal,
                        test.units,
                        test.operator
                        )

            return failstring
        
        def __repr__(self) -> str:
            return self.data.__repr__()
        
        class Test(Record.Test):

            """
            Describes single specific test, where each test is contained in a Record
            """

            def __init__(self, outer:TdrsCsv.TestDataRecord, name:str, data) -> None:
                if not isinstance(outer, TdrsCsv.TestDataRecord):
                    raise TypeError(f"exp type: {TdrsCsv.TestDataRecord}, recv type {type(outer)}")
                self._name = name
                self.data = data
                self.operator = None
                self.record = outer
                #print("self test name: ", self.name)
                self.spec = self.record.csv.test_spec[self.name]

            @property
            def name(self) -> str:
                if  '[' in self._name:
                    return re.split(r' \[', self._name)[0]
                else:
                    return self._name
            
            @property
            def status(self) -> bool:
                return True if 'PASS' in self.data else False
                
            @property
            def type(self) -> str:
                return self.spec.data_type
            
            @property
            def nominal(self) -> float:
                 return self.spec.nominal
            
            @property
            def units(self) -> str:
                return self.spec.units
            
            @property
            def low_limit(self) -> float:
                return self.spec.low_limit
            
            @property
            def high_limit(self) -> float:
                return self.spec.high_limit
            
            @property
            def meas(self):
                if self.type == "DBL":
                    try:
                        self.operator = '<>'
                        return self.record[f'{self.name} [MEAS]'].data
                    except KeyError:
                        if self.nominal in (1.0, 0.0):
                            self.operator = '=='
                            return int(not self.nominal)
                        else:
                            return None
                elif self.type == "BOOLEAN":
                    self.operator = '=='
                    return int(self.status)
                elif self.type == "STRING":
                    self.operator = '=='
                    pass #TODO: implement value for string test type
                    
                elif self.type == "CORRELATION DBL":
                    self.operator = '<>'
                    pass #TODO: implement value for CORRELATION DBL test type
