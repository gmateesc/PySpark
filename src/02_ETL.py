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

from pyspark.sql.functions import when, lit, col

from pyspark.sql.types import StringType
from pyspark.sql.types import DoubleType
from pyspark.sql.types import IntegerType



###
#
# 0. Create spark session
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
# 1. Get target data and supplier data
#
###


# Get target data from xlsx file

xlsx_file = 'inputs/Target_Data.xlsx'

print(f'\nReading target data file {xlsx_file} into dataframe tdf')

tdf = spark.read.format("com.crealytics.spark.excel") \
     .option("header", "true") \
     .option("inferSchema", "true") \
     .load(xlsx_file)




#  Get supplier data from JSON file and analyze it

json_file = 'inputs/supplier_car.json'

print(f'\nReading supplier car data file {json_file} into dataframe sdf')

sdf = spark.read.json(json_file)




###
#
# 2. Preprocess
#
###

#
# 2.1 Convert ID to integer
#

print(f'\nConvert col("ID") to Integer in sdf and show result')

sdf = sdf.withColumn("ID", sdf.ID.cast(IntegerType()) )

sdf.filter(sdf.ID<=10)[['ID','MakeText','ModelText']].groupBy('ID','MakeText','ModelText').count().orderBy('ID').show(10)




#
# 2.2 Choose among similar columns, these will be used in section
#     3.3 Select the column names of interest.
#
#     For two similar columns, we choose the one with no null values.
#

print(f'Choose among similar columns those that have no/fewer nulls')

sdf.printSchema()
"""
root
 |-- Attribute Names: string (nullable = true)
 |-- Attribute Values: string (nullable = true)
 |-- ID: integer (nullable = true)
 |-- MakeText: string (nullable = true)
 |-- ModelText: string (nullable = true)
 |-- ModelTypeText: string (nullable = true)
 |-- TypeName: string (nullable = true)
 |-- TypeNameFull: string (nullable = true)
 |-- entity_id: string (nullable = true)
"""


#
# 2.2.1 Check the make column
#

print(f'\nCheck column "MakeText" for nulls')

# 0
n = sdf.groupby(['ID','MakeText','ModelText','ModelTypeText','TypeName','TypeNameFull']).count()\
   .filter( "MakeText=='null' or MakeText is null").count()

print(f'  number of nulls in "MakeText" = {n}')




#
# 2.2.2 Check the model columns, and choose ModelTypeText
#

print(f'\nCheck columns "ModelText" and "ModelTypeText" for nulls')

# 50
n = sdf.groupby(['ID','MakeText','ModelText','ModelTypeText','TypeName','TypeNameFull']).count()\
   .filter( "ModelText=='null' or ModelText is null").count()

print(f'  number of nulls in "ModelText" = {n}')

# 0
sdf.groupby(['ID','MakeText','ModelText','ModelTypeText','TypeName','TypeNameFull']).count()\
   .filter( "ModelTypeText=='null' or ModelTypeText is null").count()
print(f'  number of nulls in "ModelTypeText" = {n}')

print(f'  choosing column "ModelTypeText"')



#
# 2.2.3 Choose the type columns, and choose TypeNameFull
#

print(f'\nCheck columns "TypeName" and "TypeNameFull" for nulls')

# 16
n = sdf.groupby(['ID','MakeText','ModelText','ModelTypeText','TypeName','TypeNameFull']).count()\
   .filter( "TypeName=='null' or TypeName is null").count()

print(f'  number of nulls in "TypeName" = {n}')


# 0
n = sdf.groupby(['ID','MakeText','ModelText','ModelTypeText','TypeName','TypeNameFull']).count()\
   .filter( "TypeNameFull=='null' or TypeNameFull is null").count()

print(f'  number of nulls in "TypeNameFull" = {n}')

print(f'  choosing column "TypeNameFull"')



#
# 2.3 Group data by the subset of columns of interest that do not contain nulls
#

print(f'\nGroup data by the subset of columns that do not contain nulls and show the number of records')

# 1153
n = sdf.groupby(['ID','MakeText','ModelTypeText','TypeNameFull']).count().orderBy('ID').count()

print(f'  number of records = {n}')






###
#
# 3. Process the supplier data
#
###


#
# 3.0 Function definitions
#

#
# 3.0.1 df_complete
#
def df_complete(df_col_unfilter, df_col_filter, col_name):

  #all_ids = df_filtered2.select('ID').distinct().rdd.flatMap(lambda x: x).collect()
  all_ids = df_col_unfilter.select('ID').distinct().rdd.flatMap(lambda x: x).collect()                  

  #attr_ids = df_filtered2a.select('ID').orderBy('ID').rdd.flatMap(lambda x: x).collect()
  attr_ids = df_col_filter.select('ID').orderBy('ID').rdd.flatMap(lambda x: x).collect()                  

  ids = list(set(all_ids) - set(attr_ids))

  data_to_add = []
  for i in ids:
    data_to_add.append( (i, 'null') )

  # Create df from data_to_add
  columns = ['ID', col_name]
  if len(data_to_add) > 0:
    df_noattr = spark.createDataFrame(data=data_to_add, schema=columns)
    df_col = df_col_filter.union(df_noattr)
  else:
    df_col = df_col_filter

  return df_col



#
# 3.0.2 harmonize_values
#
def harmonize_values(df, col_name, map):

  for cpat in map.keys():

    df = df.withColumn(col_name, \
          when( col(col_name).rlike(cpat), map[cpat] )  \
          .otherwise( df[col_name] ) )

  return df




#
# 3.1 The collection of dataframes used to build the result databframe
#

df_coll = {}



#
#
# 3.2 Select the rows with the attribute names of interest, which are the
#     attribute names that map to column names in the target.
#     They are defined in the dictionary attr_names_of_interest shown below
#

#
# 3.2.1 Define attribute names of interest 
#

attr_names_of_interest = {
  'color':     'BodyColorText',
  'carType':   'BodyTypeText',
  'city':      'City',
  'condition': 'ConditionTypeText',
  'mileage':   'Km'
}


#
# 3.2.2 Build dataframe containing the attributes of interest
#
df_filtered = sdf.filter(col('Attribute Names').isin(list(attr_names_of_interest.values())))


print(f"df_filtered =\
 sdf.filter((sdf['Attribute Names'] in ['BodyColorText','BodyTypeText','City','ConditionTypeText','Km']")

df_filtered[[
  'ID',
  'MakeText',
  'ModelTypeText',
  'TypeNameFull',
  'Attribute Names',
  'Attribute Values'
]].orderBy('ID').show(10,truncate=False)

"""
+---+-------------+-------------------------+------------------------------------+-----------------+----------------+
|ID |MakeText     |ModelTypeText            |TypeNameFull                        |Attribute Names  |Attribute Values|
+---+-------------+-------------------------+------------------------------------+-----------------+----------------+
|1  |MERCEDES-BENZ|E 320 Elégance 4-Matic   |MERCEDES-BENZ E 320 Elégance 4-Matic|BodyColorText    |anthrazit       |
|1  |MERCEDES-BENZ|E 320 Elégance 4-Matic   |MERCEDES-BENZ E 320 Elégance 4-Matic|City             |Zuzwil          |
|1  |MERCEDES-BENZ|E 320 Elégance 4-Matic   |MERCEDES-BENZ E 320 Elégance 4-Matic|ConditionTypeText|Occasion        |
|1  |MERCEDES-BENZ|E 320 Elégance 4-Matic   |MERCEDES-BENZ E 320 Elégance 4-Matic|Km               |31900           |
|1  |MERCEDES-BENZ|E 320 Elégance 4-Matic   |MERCEDES-BENZ E 320 Elégance 4-Matic|BodyTypeText     |Limousine       |
|2  |AUDI         |RS6 Avant 5.0 V10 quattro|AUDI RS6 Avant 5.0 V10 quattro      |BodyTypeText     |Kombi           |
|2  |AUDI         |RS6 Avant 5.0 V10 quattro|AUDI RS6 Avant 5.0 V10 quattro      |BodyColorText    |anthrazit       |
|2  |AUDI         |RS6 Avant 5.0 V10 quattro|AUDI RS6 Avant 5.0 V10 quattro      |City             |Zuzwil          |
|2  |AUDI         |RS6 Avant 5.0 V10 quattro|AUDI RS6 Avant 5.0 V10 quattro      |ConditionTypeText|Occasion        |
|2  |AUDI         |RS6 Avant 5.0 V10 quattro|AUDI RS6 Avant 5.0 V10 quattro      |Km               |25400           |
+---+-------------+-------------------------+------------------------------------+-----------------+----------------+
"""




#
# 3.3 Select the column names of interest
#
#       [['ID', 'MakeText', 'ModelTypeText', 'TypeNameFull']]
#
#     and group the rows by the fields that are the same for the same ID
#
#

df_coll['explicit'] = \
  df_filtered[['ID','MakeText','ModelTypeText','TypeNameFull']].groupby(['ID','MakeText','ModelTypeText','TypeNameFull']).count().drop('count')


#
# 3.4 Build the maps
#
#     [ID, col_name]  - for col_name derived from Attribute Name, i.e.,
#                       col_name in [ color, carType, city, condition, milage ]
#

for col_name in attr_names_of_interest.keys():
 
  df_ = df_filtered.withColumn(col_name, \
    when( (df_filtered['Attribute Names']==attr_names_of_interest[col_name]), df_filtered['Attribute Values'])  \
    .otherwise( lit('null') ) )

  dfa_ = df_.filter(col(col_name) != 'null')[['ID', col_name]]

  df_coll[col_name] = df_complete(df_, dfa_, col_name)




#
# 3.5 Show the collection of dataframes
#
print(f'df_coll.keys = {list(df_coll.keys())}')  
"""
df_coll.keys = ['explicit', 'color', 'carType', 'city', 'condition', 'mileage']
"""


for col_name in df_coll.keys():
  print(f"\ndf_coll[{col_name}]'.orderBy('ID').show(10)")  
  df_coll[col_name].orderBy('ID').show(10,truncate=False)

"""
df_coll[explicit]'.orderBy('ID').show(10)
+---+-------------+--------------------------------+----------------------------------------+
|ID |MakeText     |ModelTypeText                   |TypeNameFull                            |
+---+-------------+--------------------------------+----------------------------------------+
|1  |MERCEDES-BENZ|E 320 Elégance 4-Matic          |MERCEDES-BENZ E 320 Elégance 4-Matic    |
|2  |AUDI         |RS6 Avant 5.0 V10 quattro       |AUDI RS6 Avant 5.0 V10 quattro          |
|3  |AUDI         |RS6 Avant quattro               |AUDI RS6 Avant quattro                  |
|4  |CHEVROLET    |Corvette Z06                    |CHEVROLET Corvette Z06                  |
|5  |PORSCHE      |Cayenne Turbo Techart Magnum Kit|PORSCHE Cayenne Turbo Techart Magnum Kit|
|6  |FORD (USA)   |Mustang Shelby GT500            |FORD (USA) Mustang Shelby GT500         |
|7  |MERCEDES-BENZ|CLS 500                         |MERCEDES-BENZ CLS 500                   |
|8  |ASTON MARTIN |DB9 Volante                     |ASTON MARTIN DB9 Volante                |
|9  |LOTUS        |Elise                           |LOTUS Elise                             |
|10 |LAMBORGHINI  |Espada GT 400 Serie 3           |LAMBORGHINI Espada GT 400 Serie 3       |
+---+-------------+--------------------------------+----------------------------------------+


df_coll[color]'.orderBy('ID').show(10)
+---+--------------+
|ID |color         |
+---+--------------+
|1  |anthrazit     |
|2  |anthrazit     |
|3  |anthrazit     |
|4  |anthrazit     |
|5  |anthrazit     |
|6  |anthrazit mét.|
|7  |anthrazit mét.|
|8  |anthrazit mét.|
|9  |anthrazit mét.|
|10 |anthrazit mét.|
+---+--------------+


df_coll[carType]'.orderBy('ID').show(10)
+---+------------------+
|ID |carType           |
+---+------------------+
|1  |Limousine         |
|2  |Kombi             |
|3  |Kombi             |
|4  |Coupé             |
|5  |SUV / Geländewagen|
|6  |Coupé             |
|7  |Limousine         |
|8  |Cabriolet         |
|9  |Cabriolet         |
|10 |Coupé             |
+---+------------------+


df_coll[city]'.orderBy('ID').show(10)
+---+------+
|ID |city  |
+---+------+
|1  |Zuzwil|
|2  |Zuzwil|
|3  |Zuzwil|
|4  |Zuzwil|
|5  |Zuzwil|
|6  |Zuzwil|
|7  |Zuzwil|
|8  |Zuzwil|
|9  |Zuzwil|
|10 |Zuzwil|
+---+------+


df_coll[condition]'.orderBy('ID').show(10)
+---+---------+
|ID |condition|
+---+---------+
|1  |Occasion |
|2  |Occasion |
|3  |Occasion |
|4  |Occasion |
|5  |Occasion |
|6  |Occasion |
|7  |Occasion |
|8  |Occasion |
|9  |Occasion |
|10 |Oldtimer |
+---+---------+


df_coll[mileage]'.orderBy('ID').show(10)
+---+-------+
|ID |mileage|
+---+-------+
|1  |31900  |
|2  |25400  |
|3  |38500  |
|4  |200    |
|5  |2900   |
|6  |92000  |
|7  |120900 |
|8  |31800  |
|9  |38200  |
|10 |48000  |
+---+-------+
"""


#
# 3.6 Join the dataframes in the collection
#
print(f'\nJoin the dataframes in the collection df_coll into the dataframe df')

df = df_coll['explicit']
for col_name in attr_names_of_interest.keys():
  df = df.join(df_coll[col_name], on='ID', how='left')

# Show what we got
print(f"\ndf.orderBy('ID').show(10)")  
df.orderBy('ID').show(10,truncate=False)





###
#
# 4. Postprocess
#
###


#
# 4.1 Rename columns
#

# Rename map:
#   MakeText      -> make
#   ModelTypeText -> model
#   TypeNameFull  -> model_variant


print(f'\nRename the columns to match the column names in target')

print(f'Before renaming: df.columns =\n{df.columns}')
# ['ID', 'MakeText', 'ModelTypeText', 'TypeNameFull', 'color', 'carType', 'city', 'condition', 'mileage']

df = df.withColumnRenamed("MakeText", "make")\
             .withColumnRenamed("ModelTypeText", "model")\
             .withColumnRenamed("TypeNameFull", "model_variant")

print(f'After renaming: df.columns =\n{df.columns}')
# ['ID', 'make', 'model', 'model_variant', 'color', 'carType', 'city', 'condition', 'mileage']

df.orderBy('ID').show(10,truncate=False)




#
# 4.2 Add columns to supplier dataframe
#

print(f'\nAdd to supplier the missing columns, i.e., columns in target but not supplier')

#
# 4.2.1 Add column mileage_unit with value 'km'
# 

print(f"  Add column 'mileage_unit' with value 'km' to supplier")
df = df.withColumn("mileage_unit", lit('km'))



#
# 4.2.2 Add column type with value 'car'
#

print(f"  Add column 'type' with value 'car' to supplier")
df = df.withColumn("type", lit('car'))



#
# 4.2.3 Add columns that appear only in target and for which
#       a value cannot be inferred, so set to null
#

print("  Add columns currency,drive,country,manufacture_{year,month},price_on_request,zip,fuel_consumption_unit with null value")
df = df.withColumn("currency", lit('null'))\
  .withColumn("drive", lit('null'))\
  .withColumn("country", lit('null'))\
  .withColumn("manufacture_year", lit('null'))\
  .withColumn("manufacture_month", lit('null'))\
  .withColumn("price_on_request", lit('null'))\
  .withColumn("zip", lit('null'))\
  .withColumn("fuel_consumption_unit", lit('null'))



#
# 4.2.4 Reorder columns to match the order in target
#
print(f'\nReorder columns in supplier dataframe to match the order in target')
df = df.select(\
  "carType",\
  "color",\
  "condition",\
  "currency",\
  "drive",\
  "city",\
  "country",\
  "make",\
  "manufacture_year",\
  "mileage",\
  "mileage_unit",\
  "model",\
  "model_variant",\
  "price_on_request",\
  "type",\
  "zip",\
  "manufacture_month",\
  "fuel_consumption_unit"\
)


print(f'Final df.columns =\n{df.columns}')
"""
Final df.columns =
[
  'carType',
  'color',
  'condition',
  'currency',
  'drive',
  'city',
  'country',
  'make',
  'manufacture_year',
  'mileage',
  'mileage_unit',
  'model',
  'model_variant',
  'price_on_request',
  'type',
  'zip',
  'manufacture_month',
  'fuel_consumption_unit'
]
"""

print(f'tdf.columns =\n{tdf.columns}')
"""
tdf.columns =
[
  'carType', 
  'color',   
  'condition',
  'currency',
  'drive',
  'city',
  'country',
  'make',
  'manufacture_year',
  'mileage',
  'mileage_unit',
  'model',
  'model_variant',
  'price_on_request',
  'type',
  'zip',
  'manufacture_month',
  'fuel_consumption_unit'
]
"""


#
# 4.3 Harmonize the values
#

# df_good[['color']].distinct().orderBy('color').show(100)

print(f'\nHarmonize the values in supplier with those in target')


#
# 4.3.1 Harmonize the color values
#
print(f"harmonize the values in column 'color'")
color_map = {
  "anthrazit*": "Black",
  "beige*":     "Beige",
  "blau*":      "Blue",
  "bordeau*":   "Red",
  "braun*":     "Brown",
  "gelbe*":     "Yellow",
  "gold*":      "Gold", 
  "grau*":      "Gray", 
  "grün*":      "Green",
  "orange*":    "Orange",
  "silber*":    "Silver",
  "schwarz*":   "Black",
  "rot*":       "Red",
  "violett*":   "Purple",
  "weiss*":     "White",
}

df = harmonize_values(df, 'color', color_map)
df[['color']].distinct().orderBy('color').show(100, truncate=False)


#
# 4.3.2 Harmonize the carType values
#
print(f"harmonize the values in column 'carType'")

carType_map = {
  "Cabriolet":       "Convertible",
  #"Coupé":          "Coupé",  
  "Wohnkabine":      "Other",
  "Kombi":           "Station Wagon",
  "Kleinwagen":      "Other",
  "Kompakt*":        "Other",
  "Limousine":       "Saloon",
  #"Pick-up":        "Pick-up",  
  "Sattelschlepper": "Other",
  "SUV*":            "SUV",
}

df = harmonize_values(df, 'carType', carType_map)
df[['carType']].distinct().orderBy('carType').show(100, truncate=False)





#
# 5. Show final supplier dataframe
#

print(f'\nShow supplier dataframe')
df.orderBy('ID').show(4)

supplier_file = 'outputs/supplier_car_processed.csv'

print(f'\nWrite supplier dataframe into csv file {supplier_file}')
df.write.option("header", True).format("csv").mode("overwrite").save(supplier_file)
