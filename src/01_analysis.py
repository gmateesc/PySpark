#
# Run with
#
#  spark-submit --packages com.crealytics:spark-excel_2.12:3.2.1_0.17.1 src/01_analysis.py
#


#
# Import packages
#
from pyspark.sql import SparkSession
from pyspark.sql import SQLContext



###
#
# Create spark session
#
###

if __name__ == '__main__':
  spark = SparkSession \
        .builder \
        .appName("reading csv") \
        .getOrCreate()

  spark.sparkContext.setLogLevel('WARN')




###
#
# Get target data from xlsx file
#
###


xlsx_file = 'inputs/Target_Data.xlsx'

print(f'\nReading target data file {xlsx_file} into dataframe tdf')

tdf = spark.read.format("com.crealytics.spark.excel") \
     .option("header", "true") \
     .option("inferSchema", "true") \
     .load(xlsx_file)



print(f'\nShow schema of dataframe tdf')

tdf.printSchema()
"""
root
 |-- carType: string (nullable = true)
 |-- color: string (nullable = true)
 |-- condition: string (nullable = true)
 |-- currency: string (nullable = true)
 |-- drive: string (nullable = true)
 |-- city: string (nullable = true)
 |-- country: string (nullable = true)
 |-- make: string (nullable = true)
 |-- manufacture_year: string (nullable = true)
 |-- mileage: string (nullable = true)
 |-- mileage_unit: string (nullable = true)
 |-- model: string (nullable = true)
 |-- model_variant: string (nullable = true)
 |-- price_on_request: string (nullable = true)
 |-- type: string (nullable = true)
 |-- zip: string (nullable = true)
 |-- manufacture_month: string (nullable = true)
 |-- fuel_consumption_unit: string (nullable = true)
"""



print(f'Show valid mileage_unit')

tdf.select('mileage_unit').distinct().filter("mileage_unit != 'null'").show(100)
""" 
+------------+
|mileage_unit|
+------------+
|        mile|
|   kilometer|
+------------+
"""





###
#
#  Get supplier data from JSON file and analyze it
#
###

# 1. Read JSON into sdf dataframe and examine

json_file = 'inputs/supplier_car.json'

print(f'Reading supplier cat data file {json_file} into dataframe sdf')

sdf = spark.read.json(json_file)




#
# 2. Show the schema and the rows ordered by ID
#

print(f'Show schema of dataframe sdf')

sdf.printSchema()
"""
root
 |-- Attribute Names: string (nullable = true)
 |-- Attribute Values: string (nullable = true)
 |-- ID: string (nullable = true)
 |-- MakeText: string (nullable = true)
 |-- ModelText: string (nullable = true)
 |-- ModelTypeText: string (nullable = true)
 |-- TypeName: string (nullable = true)
 |-- TypeNameFull: string (nullable = true)
 |-- entity_id: string (nullable = true)
"""


# Show columns
#  ['Attribute Names','Attribute Values','ID','MakeText','ModelText','ModelTypeText','TypeName','TypeNameFull','entity_id']
#print(f'sdf.columns = \n{sdf.columns}')




#
# 3. Check granularity
#

print(f'Check granularity of records in sdf')

sdf.filter(sdf.ID=='1.0')[['ID','Attribute Names','Attribute Values']].show()
"""
+---+--------------------+----------------+
| ID|     Attribute Names|Attribute Values|
+---+--------------------+----------------+
|1.0|                  Km|           31900|
|1.0|TransmissionTypeText|         Automat|
|1.0|   ConditionTypeText|        Occasion|
|1.0|       DriveTypeText|          Allrad|
|1.0|                City|          Zuzwil|
|1.0|               Doors|               4|
|1.0|        BodyTypeText|       Limousine|
|1.0|   InteriorColorText|            grau|
|1.0|        FirstRegYear|            1999|
|1.0|          Properties|        "Ab MFK"|
|1.0|       BodyColorText|       anthrazit|
|1.0|       FirstRegMonth|               1|
|1.0|                  Hp|             224|
|1.0|ConsumptionTotalText|    11.5 l/100km|
|1.0|        FuelTypeText|          Benzin|
|1.0|               Seats|               5|
|1.0|                 Ccm|            3199|
|1.0|ConsumptionRating...|            null|
|1.0|     Co2EmissionText|        275 g/km|
+---+--------------------+----------------+
"""


#
# 4. Attribute Names
#

print(f'Show Attribute Names in sdf')
sdf[['Attribute Names']].distinct().show(truncate=False)
"""
+---------------------+
|Attribute Names      |
+---------------------+
|ConsumptionRatingText|
|FirstRegYear         |
|Doors                |
|InteriorColorText    |
|Co2EmissionText      |
|FirstRegMonth        |
|Seats                |
|ConsumptionTotalText |
|Ccm                  |
|ConditionTypeText    |
|Properties           |
|BodyColorText        |
|DriveTypeText        |
|TransmissionTypeText |
|Km                   |
|Hp                   |
|BodyTypeText         |
|FuelTypeText         |
|City                 |
+---------------------+
"""

