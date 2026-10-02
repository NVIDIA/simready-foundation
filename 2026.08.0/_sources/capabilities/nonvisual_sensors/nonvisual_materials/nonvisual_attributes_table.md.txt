# Non-Visual Sensor Attributes Table

This table represents the overall list of valid, measured values that can be applied to the Non-Visual Sensor attributes. Each section (base, coating, attributes) contains the listing of allowed values that can be input.

## Base

| Index | USD Label | Meaning |
|-------|-----------|---------|
|0|none|Default, unlabeled or unspecified material|
|**Metals:**|||
|1|aluminum|Signs, poles, etc.|
|2|steel|Heavy construction metals, bridges, etc.|
|3|oxidized_steel|Rusted steel|
|4|iron|Manhole covers, drainage grills, etc.|
|5|oxidized_iron|Rusted iron|
|6|silver|Shiny metals|
|7|brass|Architecture|
|8|bronze|Statues, etc.|
|9| oxidized_Bronze_Patina|Old statues|
|10|tin|Food, Cans, etc.|
|**Polymers**|||
|11|plastic|Generic plastic, etc.|
|12|fiberglass|Car bumpers, etc.|
|13|carbon_fiber|Car parts, bicycle parts, etc.|
|14|vinyl|Car insides, etc.|
|15|plexiglass|Light covers, etc.|
|16|pvc|Water tubes, etc.|
|17|nylon|Plastic bags, etc.|
|18|polyester|Some clothing, etc.|
|**Glass**|||
|19|clear_glass|Glass that is clear with no contaminants|
|20|frosted_glass|Glass that has any volumetric particulates|
|21|one_way_mirror|Buildings glass panels|
|22|mirror|Car side mirrors, etc.|
|23|ceramic_glass|Heavy duty glass in construction|
|**Other**|||
|24|asphalt|Roads, etc.|
|25|concrete|Construction, sidewalks, etc.|
|26|leaf_grass|Live vegetation|
|27|dead_leaf_grass|Dead vegetation|
|28|rubber|Tires, etc.|
|29|wood|Construction timber|
|30|bark|Vegetation|
|31|cardboard|Boxes, etc.|
|32|paper|Newspapers, paper bags, etc.|
|33|fabric|Clothing, flags, etc.|
|34|skin|Humans, animals, etc.|
|35|fur_hair|Human head, animals, etc.|
|36|leather|Clothing, car insides, etc.|
|37|marble|Construction|
|38|brick|Construction|
|39|stone|Nature, stones that have geometry|
|40|gravel|Nature, finer stones that are maps|
|41|dirt|Nature, even finer stones/dust, ground, etc.|
|42|mud|Nature, wet dirt|
|43|water|Nature, water fountains, etc.|
|44|salt_water|Nature|
|45|snow|Nature|
|46|ice|Nature|
|47|calibration_lambertian|Special material for special assets with defined diffuse reflectance set in MDL with special values. Content creators need to care for these values and for applying the material only on select assets. Ex: target panels, corner reflectors, etc.|
|...|...|Reserved for future expansion|

## Coating

| Index | USD Label | Meaning |
|-------|-----------|---------|
|0|none|Default, unlabeled or unspecified coating|
|1|paint|Painted surface|
|2|clearcoat|Clear-coated surface|
|3|paint_clearcoat|Painted and Clear-coated|
|...|...|Reserved for future expansion|

## Attributes

| Index | USD Label | Meaning |
|-------|-----------|---------|
|0|none|No attributes specified|
|1|emissive|Energy-emitting surface e.g. lights, sign panels, etc.|
|2|retroreflective|Retroreflective surface e.g.- safety vests, road reflectors, etc.|
|3|single_sided|Single-sided (non-thin geometry)|
|4|visually_transparent|Material is visually transparent, e.g. - glass, etc.|
|...|...|Reserved for future expansion|
