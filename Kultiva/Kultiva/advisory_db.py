from django.utils.translation import gettext_lazy as _

CROP_ADVISORY_DB = {
    # -----------------------------------------------------------------
    # CEREALS
    # -----------------------------------------------------------------
    "Rice": {
        "season": "Kharif",
        "soil_prep": "Prepare the land by plowing 2-3 times, followed by harrowing to create a fine tilth; level the field to ensure uniform water distribution. Incorporate 10-12 tons of Farm Yard Manure (FYM) or compost into the soil during the last plowing to enhance fertility.",
        "growth_stages": {
            "Seedling (0-30 days)": "Maintain a water level of 2-5 cm in the main field after transplanting to prevent weed growth and ensure proper establishment. Apply a starter dose of nitrogen and protect seedlings from birds.",
            "Vegetative (30-60 days)": "Increase water depth to 5 cm as the plant grows, ensuring the soil remains continuously submerged. This is a critical period for tillering, so ensure nutrient availability and monitor for early signs of stem borer.",
            "Flowering/Fruiting (60-90+ days)": "Maintain a consistent 5 cm water level during flowering and grain filling, as water stress at this stage can severely impact yield. Reduce water 10-15 days before harvesting to allow for uniform drying of grains."
        },
        "fertilizer_schedule": {
            "Basal Dose (At Sowing/Transplanting)": "NPK Ratio: 120:60:60 kg/ha. Apply full dose of Phosphorus (P) and Potassium (K) along with 1/3 of Nitrogen (N). Organic: 12.5 tons/ha of FYM or compost.",
            "Top Dressing 1": "Apply 1/3 of Nitrogen (N) at the active tillering stage, approximately 25-30 days after transplanting.",
            "Top Dressing 2": "Apply the final 1/3 of Nitrogen (N) at the panicle initiation stage, around 55-60 days after transplanting."
        },
        "irrigation_plan": "Rice requires continuous standing water. Irrigate to maintain a 2-5 cm water level from transplanting until the grains are in the dough stage. Stop irrigation about two weeks before the intended harvest date.",
        "pest_disease_management": [
            {"threat": "Stem Borer", "solution": "Chemical: Spray Cartap Hydrochloride 4G. Organic: Use pheromone traps to monitor and catch male moths; encourage natural predators like spiders and dragonflies."},
            {"threat": "Brown Planthopper (BPH)", "solution": "Chemical: Apply Imidacloprid or Thiamethoxam at the base of the plants. Organic: Release natural predators like mirid bugs and spiders; maintain proper spacing for aeration."},
            {"threat": "Blast Disease", "solution": "Chemical: Spray Tricyclazole or Azoxystrobin as a preventive measure. Organic: Use resistant varieties; ensure balanced nutrient application to avoid excessive nitrogen."}
        ],
        "harvest_indicators": "Harvest when 80-85% of the panicles have turned golden yellow and the grains have a moisture content of 20-25%. The upper part of the panicle should be drooping and the grains firm when pressed."
    },
    "Maize": {
        "season": "Kharif & Rabi",
        "soil_prep": "The field should be plowed to a depth of 15-20 cm to achieve a fine tilth, ensuring good aeration and drainage. Incorporate 10-15 tons of well-decomposed FYM into the soil 2-3 weeks before sowing to improve soil structure and fertility.",
        "growth_stages": {
            "Seedling (0-30 days)": "Ensure the field is free from weeds to reduce competition for nutrients. Light and frequent irrigation is crucial for good germination and seedling establishment.",
            "Vegetative (30-60 days)": "This is the grand growth period; ensure adequate nitrogen supply for rapid foliage development. Earthing up should be done around 30-35 days after sowing to provide support and control weeds.",
            "Flowering/Fruiting (60-90+ days)": "The tasseling and silking stages are critical for water requirements; water stress can lead to poor pollination and grain filling. Protect the cobs from pests like the fall armyworm."
        },
        "fertilizer_schedule": {
            "Basal Dose (At Sowing)": "NPK Ratio: 150:75:75 kg/ha. Apply 1/3 of Nitrogen (N) and the full dose of Phosphorus (P) and Potassium (K). Organic: 15 tons/ha of FYM and 250 kg/ha of Neem Cake.",
            "Top Dressing 1": "Apply 1/3 of Nitrogen (N) when the plants are knee-high, approximately 25-30 days after sowing.",
            "Top Dressing 2": "Apply the remaining 1/3 of Nitrogen (N) at the pre-tasseling stage, around 45-50 days after sowing."
        },
        "irrigation_plan": "Maize is sensitive to both waterlogging and drought. Irrigate at critical stages: early vegetative, tasseling (flowering), and grain filling. Generally, irrigation is needed every 8-10 days depending on soil type and weather.",
        "pest_disease_management": [
            {"threat": "Fall Armyworm", "solution": "Chemical: Spray Spinetoram or Emamectin Benzoate. Organic: Apply sand mixed with ash into the whorl; use pheromone traps for monitoring."},
            {"threat": "Maize Stem Borer", "solution": "Chemical: Apply granules of Carbofuran 3G in the plant whorls. Organic: Encourage parasitic wasps (Trichogramma); remove and destroy infected plant parts."},
            {"threat": "Turcicum Leaf Blight", "solution": "Chemical: Spray Mancozeb or Propiconazole at the appearance of initial symptoms. Organic: Use resistant varieties and practice crop rotation."}
        ],
        "harvest_indicators": "Harvest for grain when the outer husk of the cobs turns from green to white/yellowish and the silks have dried and turned brown. Grains will be hard and have a moisture content of about 20-25%."
    },
    # -----------------------------------------------------------------
    # PULSES
    # -----------------------------------------------------------------
    "ChickPea": {
        "season": "Rabi",
        "soil_prep": "The field should be well-pulverized and leveled, with one deep plowing followed by 2-3 harrowings. Ensure the soil has good moisture content at the time of sowing as it is primarily a rainfed crop.",
        "growth_stages": {
            "Seedling (0-30 days)": "Weed control is critical during the initial 3-4 weeks to prevent competition. A light irrigation may be necessary if there is insufficient residual soil moisture for establishment.",
            "Vegetative (30-60 days)": "Nipping or topping the apical buds around 30-35 days after sowing encourages branching and increases the number of pods.",
            "Flowering/Fruiting (60-90+ days)": "This is a critical stage for water requirement; provide one irrigation at pre-flowering and another at the pod development stage for optimal yield. Monitor for pod borer activity."
        },
        "fertilizer_schedule": {
            "Basal Dose (At Sowing)": "NPK Ratio: 20:60:20 kg/ha. Apply the full dose of N, P, and K at the time of sowing. Organic: 5 tons/ha of FYM and seed treatment with Rhizobium culture.",
            "Top Dressing 1": "Generally not required as it is a legume. A foliar spray of 2% Urea or DAP can be applied if deficiency symptoms appear.",
            "Top Dressing 2": "Not applicable for this crop."
        },
        "irrigation_plan": "Chickpea is mostly grown as a rainfed crop. If irrigation is available, provide one pre-sowing irrigation and then one at the pre-flowering stage and another critical one at the pod-filling stage.",
        "pest_disease_management": [
            {"threat": "Pod Borer (Helicoverpa armigera)", "solution": "Chemical: Spray Emamectin Benzoate 5% SG. Organic: Install pheromone traps; spray Neem Seed Kernel Extract (NSKE) 5%."},
            {"threat": "Wilt (Fusarium oxysporum)", "solution": "Chemical: Seed treatment with Thiram + Carbendazim. Organic: Use resistant varieties; practice deep summer plowing and a 4-5 year crop rotation."},
            {"threat": "Rust", "solution": "Chemical: Spray Mancozeb or Propiconazole. Organic: Use rust-resistant varieties and remove infected plant debris after harvest."}
        ],
        "harvest_indicators": "The crop is ready for harvest when the leaves turn yellowish-brown and start to shed. The pods should be dry and rattle when shaken."
    },
    "KidneyBeans": {
        "season": "Rabi & Kharif (in hills)",
        "soil_prep": "Prepare a well-drained, clod-free seedbed by plowing the land 2-3 times. Level the field properly to facilitate uniform irrigation and germination.",
        "growth_stages": {
            "Seedling (0-30 days)": "Ensure consistent moisture for uniform germination; the crop is sensitive to waterlogging. Keep the field weed-free during the initial 25-30 days.",
            "Vegetative (30-60 days)": "Provide support or staking for pole-type varieties. A light earthing up can be done to provide support to the plants.",
            "Flowering/Fruiting (60-90+ days)": "Flowering and pod formation are critical stages for irrigation. Avoid water stress to prevent flower drop and ensure proper bean development."
        },
        "fertilizer_schedule": {
            "Basal Dose (At Sowing)": "NPK Ratio: 100:60:40 kg/ha. Apply half dose of Nitrogen (N) and the full dose of Phosphorus (P) and Potassium (K). Organic: 10-15 tons/ha of FYM.",
            "Top Dressing 1": "Apply the remaining half of Nitrogen (N) about 30 days after sowing, at the time of the first weeding and earthing up.",
            "Top Dressing 2": "Not applicable for this crop."
        },
        "irrigation_plan": "Irrigate immediately after sowing and then a light irrigation on the 3rd day. Subsequently, irrigate every 8-12 days, paying special attention to the flowering and pod-filling stages.",
        "pest_disease_management": [
            {"threat": "Bean Aphids", "solution": "Chemical: Spray Dimethoate or Imidacloprid. Organic: Release ladybugs as predators; spray a solution of neem oil and soap."},
            {"threat": "Anthracnose", "solution": "Chemical: Spray Carbendazim or Mancozeb. Organic: Use certified disease-free seeds; practice crop rotation and remove infected plant parts."},
            {"threat": "Bean Common Mosaic Virus (BCMV)", "solution": "Chemical: Control the aphid vector with systemic insecticides. Organic: Use virus-resistant varieties; remove and destroy infected plants immediately."}
        ],
        "harvest_indicators": "For green beans, harvest when pods are tender and seeds are not fully developed. For dry beans, harvest when the pods turn yellow or brown and the leaves have fallen off."
    },
    "PigeonPeas": {
        "season": "Kharif",
        "soil_prep": "The land should be plowed once or twice to get a fine tilth, as a cloddy field can affect germination. Ensure the field is well-leveled and has adequate drainage, especially for the rainy season crop.",
        "growth_stages": {
            "Seedling (0-30 days)": "Maintain a weed-free environment for the first 4-6 weeks as the crop grows slowly in its initial stages. Thinning may be required to maintain optimal plant population.",
            "Vegetative (30-60 days)": "The crop exhibits rapid vegetative growth during this period. Inter-cultivation can be done to control weeds and improve soil aeration.",
            "Flowering/Fruiting (60-90+ days)": "This is a critical phase sensitive to moisture stress and pests. One protective irrigation during this phase can significantly boost yields if there is a dry spell."
        },
        "fertilizer_schedule": {
            "Basal Dose (At Sowing)": "NPK Ratio: 20:40:20 kg/ha. Apply the full dose of all fertilizers at the time of sowing. Organic: Seed treatment with Rhizobium and Phosphate Solubilizing Bacteria (PSB) culture.",
            "Top Dressing 1": "Generally not required. If the crop shows signs of nitrogen deficiency, a foliar spray of 2% urea can be beneficial.",
            "Top Dressing 2": "Not applicable for this crop."
        },
        "irrigation_plan": "Pigeonpea is a hardy, drought-tolerant crop often grown rainfed. If irrigation is available, one irrigation at flowering and another at the pod-filling stage can increase yield by 40-50%.",
        "pest_disease_management": [
            {"threat": "Pod Borer Complex (Helicoverpa, Maruca)", "solution": "Chemical: Spray Indoxacarb or Spinosad. Organic: Use pheromone traps for monitoring; spray NSKE 5% or Bacillus thuringiensis (Bt)."},
            {"threat": "Sterility Mosaic Disease", "solution": "Chemical: Control the mite vector with Dicofol or wettable sulfur. Organic: Use resistant varieties; remove and destroy infected plants."},
            {"threat": "Wilt (Fusarium udum)", "solution": "Chemical: Seed treatment with Trichoderma viride. Organic: Use wilt-resistant varieties; practice intercropping with sorghum and a long-term crop rotation."}
        ],
        "harvest_indicators": "Harvest when 75-80% of the pods turn brown and dry. Over-maturity can lead to shattering of pods in the field."
    },
    "MothBeans": {
        "season": "Kharif",
        "soil_prep": "The crop requires a well-pulverized seedbed, which can be achieved with one plowing followed by 2-3 cross harrowings. The field should be clean, leveled, and free from weeds before sowing.",
        "growth_stages": {
            "Seedling (0-30 days)": "Initial growth is slow, making weed control essential for the first 3-4 weeks. One hand weeding or inter-culture operation is recommended.",
            "Vegetative (30-60 days)": "The plant develops a trailing or semi-erect growth habit, covering the ground. It is highly drought-resistant during this phase.",
            "Flowering/Fruiting (60-90+ days)": "Flowering and podding occur over an extended period. The crop can withstand dry spells but a late-season rain can be very beneficial for pod filling."
        },
        "fertilizer_schedule": {
            "Basal Dose (At Sowing)": "NPK Ratio: 10:20:0 kg/ha. Apply the full recommended dose of fertilizers as a basal application. Organic: Seed inoculation with a specific Rhizobium culture is highly recommended.",
            "Top Dressing 1": "Not required or recommended for this crop.",
            "Top Dressing 2": "Not applicable for this crop."
        },
        "irrigation_plan": "Moth Bean is an extremely drought-tolerant crop grown exclusively under rainfed conditions. It does not require any irrigation.",
        "pest_disease_management": [
            {"threat": "Whitefly", "solution": "Chemical: Spray Thiamethoxam or Acetamiprid. Organic: Use yellow sticky traps; spray neem oil solution."},
            {"threat": "Yellow Mosaic Virus", "solution": "Chemical: Control the whitefly vector with systemic insecticides. Organic: Use resistant varieties and remove infected plants to stop the spread."},
            {"threat": "Hairy Caterpillar", "solution": "Chemical: Dusting with Malathion 5% dust. Organic: Collect and destroy egg masses and young larvae; set up light traps."}
        ],
        "harvest_indicators": "Harvesting should be done when the pods turn dull brown or blackish and become dry. Do not delay harvesting to avoid pod shattering."
    },
    "MungBean": {
        "season": "Kharif & Zaid",
        "soil_prep": "The field should be prepared to a fine tilth by giving one plowing followed by two harrowings. Proper leveling is essential for good drainage, especially during the Kharif season.",
        "growth_stages": {
            "Seedling (0-30 days)": "Timely weeding within the first 20-25 days is crucial as weeds compete heavily for nutrients, light, and moisture.",
            "Vegetative (30-60 days)": "The plant undergoes vegetative growth and starts branching. The crop requires a dry and clean environment to prevent fungal diseases.",
            "Flowering/Fruiting (60-90+ days)": "The flowering and pod-setting stages are critical for moisture. A light irrigation at this stage can significantly improve pod length and grain weight."
        },
        "fertilizer_schedule": {
            "Basal Dose (At Sowing)": "NPK Ratio: 20:40:20 kg/ha. Apply the full amount of fertilizers at sowing time. Organic: Treat seeds with Rhizobium culture; apply 5 tons/ha of FYM.",
            "Top Dressing 1": "Not generally recommended. A foliar spray of 2% DAP at the pre-flowering stage can be applied for better pod setting.",
            "Top Dressing 2": "Not applicable for this crop."
        },
        "irrigation_plan": "The crop needs 2-3 irrigations. The first should be given 20-25 days after sowing, and the second at the flowering/pod formation stage (45-50 days). Avoid water stress during these critical phases.",
        "pest_disease_management": [
            {"threat": "Whitefly & Aphids", "solution": "Chemical: Spray Imidacloprid or Thiamethoxam. Organic: Use yellow sticky traps; spray neem oil or insecticidal soap."},
            {"threat": "Yellow Mosaic Virus", "solution": "Chemical: Control the whitefly vector. Organic: Use tolerant/resistant varieties; uproot and destroy infected plants early."},
            {"threat": "Cercospora Leaf Spot", "solution": "Chemical: Spray Carbendazim or Mancozeb. Organic: Use disease-free seeds; practice crop rotation and field sanitation."}
        ],
        "harvest_indicators": "The crop matures in 65-90 days. Harvest when about 80% of the pods turn blackish and feel dry. Two to three pickings may be required as all pods do not mature at the same time."
    },
    "Blackgram": {
        "season": "Kharif & Rabi (rice fallows)",
        "soil_prep": "The land should be well-prepared with 1-2 plowings to achieve a fine, weed-free seedbed. Proper leveling is important to avoid water stagnation in the field.",
        "growth_stages": {
            "Seedling (0-30 days)": "Weed management in the first 30 days is vital for healthy crop establishment. A pre-emergence herbicide or one hand weeding can be done.",
            "Vegetative (30-60 days)": "The crop enters a rapid growth phase. Ensure good aeration and drainage to prevent root diseases.",
            "Flowering/Fruiting (60-90+ days)": "This stage is critical for water. Moisture stress can lead to significant flower drop and reduced pod filling."
        },
        "fertilizer_schedule": {
            "Basal Dose (At Sowing)": "NPK Ratio: 20:40:20 kg/ha. Full dose of NPK should be drilled at the time of sowing. Organic: Apply 5 tons/ha of FYM and treat seeds with Rhizobium culture.",
            "Top Dressing 1": "Not required. However, a foliar spray of 2% DAP at peak flowering can enhance pod formation.",
            "Top Dressing 2": "Not applicable for this crop."
        },
        "irrigation_plan": "Usually grown as a rainfed crop. If necessary, one irrigation can be provided at the flowering stage and another at the pod development stage for higher yields.",
        "pest_disease_management": [
            {"threat": "Pod Borer", "solution": "Chemical: Spray with Profenofos or Chlorantraniliprole. Organic: Spray NSKE 5%; encourage natural predators."},
            {"threat": "Yellow Mosaic Virus", "solution": "Chemical: Control the whitefly vector using Thiamethoxam. Organic: Rogue out infected plants; grow resistant varieties."},
            {"threat": "Powdery Mildew", "solution": "Chemical: Spray wettable sulfur or Dinocap. Organic: Dusting with sulfur powder; ensure proper plant spacing for air circulation."}
        ],
        "harvest_indicators": "The crop is ready for harvest when the pods turn black and become brittle. The plants are cut at the ground level, stacked for a few days to dry, and then threshed."
    },
    "Lentil": {
        "season": "Rabi",
        "soil_prep": "Prepare the land to a fine tilth by one plowing followed by 2-3 harrowings. The seedbed must be firm and moist to ensure good germination.",
        "growth_stages": {
            "Seedling (0-30 days)": "Initial 4-5 weeks are critical for weed control. Ensure the young seedlings are not competing with weeds for resources.",
            "Vegetative (30-60 days)": "Branching and vegetative growth pick up. It's a low-growing plant, so a clean field helps in better growth.",
            "Flowering/Fruiting (60-90+ days)": "Provide a light irrigation at the pre-flowering stage if winter rains fail. This is the most sensitive stage to moisture stress."
        },
        "fertilizer_schedule": {
            "Basal Dose (At Sowing)": "NPK Ratio: 20:60:20 kg/ha. Drill the entire quantity of fertilizers at the time of sowing. Organic: Seed treatment with Rhizobium and PSB is highly beneficial.",
            "Top Dressing 1": "Not required for this crop.",
            "Top Dressing 2": "Not applicable for this crop."
        },
        "irrigation_plan": "Mostly cultivated as a rainfed crop on residual moisture. If irrigation is available, one irrigation at 45 days after sowing and another at the pod-filling stage is recommended.",
        "pest_disease_management": [
            {"threat": "Aphids", "solution": "Chemical: Spray Dimethoate or Imidacloprid. Organic: Encourage ladybugs and lacewings; spray neem oil solution."},
            {"threat": "Rust", "solution": "Chemical: Spray with Mancozeb twice at a 10-day interval. Organic: Use rust-resistant varieties and maintain field sanitation."},
            {"threat": "Wilt", "solution": "Chemical: Seed treatment with Thiram. Organic: Practice a 3-4 year crop rotation; use wilt-resistant varieties."}
        ],
        "harvest_indicators": "Harvest the crop when the plants start to dry, leaves have fallen, and 80% of the pods are ripe and make a rattling sound. Over-ripening will lead to shattering losses."
    }
},
CROP_ADVISORY_DB_FRUITS = {
    # -----------------------------------------------------------------
    # FRUITS
    # -----------------------------------------------------------------
    "Pomegranate": {
        "season": "Perennial",
        "soil_prep": "Dig pits of 60x60x60 cm one month prior to planting and expose to sunlight to kill pests. Fill the pits with a mixture of topsoil, 20 kg of FYM, and 1 kg of single super phosphate.",
        "growth_stages": {
            "Establishment (Year 1)": "Focus on vegetative growth and frame development. Irrigate regularly and protect the young plant from pests and diseases.",
            "Juvenile/Vegetative (Year 2-3)": "Continue training and light pruning to develop a strong framework. Start applying a balanced dose of fertilizers to encourage growth.",
            "Fruiting/Mature (Year 4+)": "Induce stress by withholding water before flowering (Ambe bahar treatment). Manage nutrition and irrigation carefully during fruit development to avoid fruit cracking."
        },
        "fertilizer_schedule": {
            "Basal Dose (At Planting)": "20 kg FYM + 500g Single Super Phosphate + 100g Potash per pit.",
            "Top Dressing 1 (Per Year of Age, split)": "Apply 10-15 kg FYM, 100-200g N, 50-100g P, and 50-100g K per plant. First split after pruning in spring.",
            "Top Dressing 2 (Per Year of Age, split)": "Apply the second split of chemical fertilizers 3-4 weeks after the first application, during active growth or fruit development."
        },
        "irrigation_plan": "Drip irrigation is highly recommended. Irrigate young plants every 2-3 days. For mature trees, irrigate at 4-5 day intervals during fruit development. Withhold irrigation for 1-2 months before inducing flowering stress.",
        "pest_disease_management": [
            {"threat": "Anar Butterfly (Fruit Borer)", "solution": "Chemical: Spray Spinosad or Emamectin Benzoate during flowering. Organic: Bag individual fruits with paper or cloth bags; remove and destroy infested fruits."},
            {"threat": "Bacterial Blight", "solution": "Chemical: Spray with a combination of Streptocycline and Copper Oxychloride. Organic: Prune and burn affected twigs; use disease-resistant varieties like 'Bhagwa'."}
        ],
        "harvest_indicators": "The fruit skin turns from green to a slightly yellowish-red or full red depending on the variety. Fruits produce a metallic sound when tapped, and the calyx at the bottom dries and curls inwards."
    },
    "Banana": {
        "season": "Perennial (planted year-round)",
        "soil_prep": "Deep plow the land and prepare pits of 45x45x45 cm. Fill pits with topsoil mixed with 10-15 kg of well-decomposed FYM, 250 g of Neem cake, and 20 g of Carbofuran.",
        "growth_stages": {
            "Sucker to Vegetative (0-5 months)": "Ensure frequent irrigation for proper establishment. Apply high nitrogen fertilizer every month and carry out 'desuckering' to retain only one healthy follower sucker.",
            "Shooting/Flowering (6-8 months)": "This is the 'shooting' stage where the flower emerges. Provide propping support with bamboo to the plant to prevent lodging. Ensure consistent moisture.",
            "Bunch Development (9-12 months)": "Potassium requirement is highest during this stage. Cover the bunch with skerting bags to protect from pests and sunburn, which improves quality."
        },
        "fertilizer_schedule": {
            "Basal Dose (At Planting)": "10 kg FYM + 250g Neem Cake per pit.",
            "Top Dressing 1 (Fertigation Schedule)": "High NPK requirement (200g N, 100g P, 300g K per plant per year). Apply in 5-6 split doses through fertigation or as soil application every 2 months.",
            "Top Dressing 2": "A foliar spray of Sulphate of Potash (1%) at the time of bunch formation helps in improving the size and quality of fingers."
        },
        "irrigation_plan": "Banana is a high water-consuming crop. Irrigate every 4-5 days during dry seasons and 7-8 days during winter. Drip irrigation is the most efficient method to maintain consistent moisture.",
        "pest_disease_management": [
            {"threat": "Rhizome Weevil", "solution": "Chemical: Drenching the soil with Chlorpyrifos. Organic: Use clean, healthy suckers for planting; apply neem cake in the pit during planting."},
            {"threat": "Sigatoka Leaf Spot", "solution": "Chemical: Spray Propiconazole or Mancozeb alternately. Organic: Remove and burn severely affected older leaves; maintain proper field sanitation and spacing."},
            {"threat": "Panama Wilt", "solution": "Chemical: No effective chemical control. Organic: Use resistant varieties like 'Grand Naine' (G9); practice crop rotation; improve soil drainage."}
        ],
        "harvest_indicators": "Harvest when the bunch is fully developed, the ridges on the fruit surface change from angular to round, and the color of the fruit turns from dark green to light green. The top leaves start to dry and wither."
    },
    "Mango": {
        "season": "Perennial",
        "soil_prep": "Plough the field deeply and prepare pits of 1x1x1 meter in size during the summer to expose them to the sun. Fill the pits with a mixture of topsoil, 30-40 kg FYM, 2.5 kg single super phosphate, and 1 kg Muriate of Potash.",
        "growth_stages": {
            "Establishment (Year 1-3)": "Focus on creating a strong framework by training the young plants. Irrigate regularly and protect from pests like stem borer and leaf-eating caterpillars.",
            "Juvenile/Vegetative (Year 4-7)": "The tree gains size and canopy develops. Pruning of criss-cross and diseased branches should be done after the rainy season.",
            "Fruiting/Mature (Year 8+)": "Withhold irrigation 2-3 months prior to flowering to induce stress. Resume irrigation after fruit set (pea size) to support development. Critical to manage hoppers at flowering."
        },
        "fertilizer_schedule": {
            "Basal Dose (At Planting)": "30-40 kg FYM in the pit.",
            "Top Dressing 1 (Post-Harvest - June/July)": "For a mature tree (>10 years), apply 50-100 kg FYM along with 1.5-2.0 kg Urea, 2.0-2.5 kg SSP, and 1.0-1.5 kg MOP in a ring around the tree.",
            "Top Dressing 2": "Not a standard practice, but foliar sprays of Potassium Nitrate (1%) or NAA before flowering can enhance it. A post-fruit set spray of micronutrients is also beneficial."
        },
        "irrigation_plan": "Irrigate young plants once every 3-4 days. For bearing trees, stop irrigation from October to December. Resume light irrigation at the fruit set stage and continue every 10-15 days until the monsoon begins.",
        "pest_disease_management": [
            {"threat": "Mango Hopper", "solution": "Chemical: Spray Imidacloprid or Thiamethoxam at the time of panicle emergence. Organic: Use sticky traps; spray with neem oil as a repellent."},
            {"threat": "Powdery Mildew", "solution": "Chemical: Spray with wettable sulphur or Dinocap when panicles are 8-10 cm long. Organic: Dust sulphur powder in the morning; prune for better air circulation."}
        ],
        "harvest_indicators": "Harvest fruits when they are fully developed, have a slight color change at the shoulder from dark green to light yellow, and a few ripe fruits fall naturally from the tree (known as 'tapka')."
    },
    "Grapes": {
        "season": "Perennial",
        "soil_prep": "The land should be leveled and plowed 2-3 times to a depth of 45-60 cm to ensure good drainage. Erect the training system, like bower or T-trellis, before planting the rooted cuttings.",
        "growth_stages": {
            "Foundation Pruning & Growth (April-Sept)": "After the harvest in April, a 'foundation pruning' is done, leaving 1-2 buds on the cane. This phase is for vegetative growth and cane maturation.",
            "Fruit Pruning & Sprouting (Oct-Nov)": "In October, the canes are pruned again ('fruit pruning'). The number of buds left depends on the variety. This pruning induces fruiting.",
            "Flowering to Harvest (Nov-March)": "This is the main fruiting season. Critical management of water, nutrients (especially potassium), and diseases like powdery and downy mildew is required."
        },
        "fertilizer_schedule": {
            "Basal Dose (Post Foundation Pruning)": "Apply a heavy dose of FYM (50-60 kg/plant) along with a high nitrogen fertilizer.",
            "Top Dressing 1 (During Berry Growth)": "Fertigation is key. Apply a high potassium fertilizer schedule from the pea-size stage to the veraison (color change) stage to improve size and TSS.",
            "Top Dressing 2": "Foliar sprays of calcium and boron are important during berry development to prevent cracking and improve quality."
        },
        "irrigation_plan": "Drip irrigation is standard practice. Irrigate daily based on pan evaporation data. Withhold water for a stress period before the October 'fruit pruning' and reduce irrigation as the berries approach maturity to increase sugar content (TSS).",
        "pest_disease_management": [
            {"threat": "Powdery Mildew", "solution": "Chemical: Regular prophylactic sprays of wettable sulphur, Myclobutanil, or Penconazole. Organic: Spray with biologicals like Ampelomyces quisqualis; ensure good canopy ventilation."},
            {"threat": "Downy Mildew", "solution": "Chemical: Prophylactic sprays of Mancozeb and curative sprays of Metalaxyl + Mancozeb. Organic: Bordeaux mixture application; avoid overhead irrigation and improve air circulation."}
        ],
        "harvest_indicators": "Harvest based on Total Soluble Solids (TSS), typically 18-24 °Brix depending on the variety. Berries develop their characteristic color, aroma, and become less acidic. The bunch should be firm and berries should not be soft."
    },
    "Apple": {
        "season": "Perennial",
        "soil_prep": "Prepare pits of 1x1x1 meter in autumn and leave them open for a fortnight. Fill the pits with a mix of topsoil, 40 kg of well-rotted FYM, and 1 kg of superphosphate before winter sets in.",
        "growth_stages": {
            "Establishment (Year 1-2)": "After planting, the primary focus is on survival and establishment. Provide a stake for support and protect the trunk from sunburn and cold injury.",
            "Training & Pruning (Year 3-5)": "Train the tree to a modified central leader system. Annual pruning during dormancy (Dec-Jan) is critical to develop a strong scaffold and encourage fruiting spurs.",
            "Full Bearing (Year 6+)": "The tree enters full production. Focus on maintaining a balance between vegetative growth and fruiting through judicial pruning, nutrient management, and fruit thinning."
        },
        "fertilizer_schedule": {
            "Basal Dose (At Planting)": "40 kg FYM + 1 kg Superphosphate in the pit.",
            "Top Dressing 1 (Spring Application)": "For mature trees, apply 20-25 kg FYM, 500g N, 250g P, and 500g K in the basin area, about 3-4 weeks before bud break.",
            "Top Dressing 2": "A post-harvest application of Urea (1-2%) as a foliar spray helps build nitrogen reserves for the next season."
        },
        "irrigation_plan": "Irrigate the basin every 7-10 days during the peak growing season from April to August. Ensure irrigation at critical stages like 'fruit set' and 'fruit development'. Reduce watering before harvest to improve quality.",
        "pest_disease_management": [
            {"threat": "Apple Scab", "solution": "Chemical: A strict spray schedule with fungicides like Mancozeb, Captan, and Myclobutanil from the 'green tip' stage onwards. Organic: Use resistant varieties; collect and destroy fallen leaves in autumn."},
            {"threat": "Codling Moth", "solution": "Chemical: Spray with insecticides like Chlorantraniliprole based on pheromone trap catches. Organic: Use pheromone traps for mass trapping and mating disruption; encourage natural predators."}
        ],
        "harvest_indicators": "The fruit attains its characteristic size and color for the variety. The ground color of the skin changes from green to pale yellow. The seeds turn brown, and the fruit separates easily from the spur with a gentle upward twist."
    },
    "Orange": {
        "season": "Perennial",
        "soil_prep": "Plough the land thoroughly and dig pits of 75x75x75 cm a month before planting. Fill the pits with topsoil mixed with 15-20 kg of FYM and 500 g of single super phosphate.",
        "growth_stages": {
            "Establishment (Year 1-3)": "Provide regular irrigation and protect young plants from pests like leaf miner and psylla. Prune water sprouts and dead wood to shape the plant.",
            "Vegetative Growth (Year 4-5)": "The canopy develops and the tree prepares for commercial bearing. Ensure balanced nutrition to support this growth.",
            "Fruiting (Year 6+)": "Manage irrigation and nutrition during the three main flushes of growth and flowering ('bahars'). Protect the developing fruits from fruit flies and fruit sucking moths."
        },
        "fertilizer_schedule": {
            "Basal Dose (At Planting)": "15 kg FYM + 500g SSP per pit.",
            "Top Dressing 1 (Pre-Monsoon)": "For a mature tree, apply half the dose of NPK (e.g., 750g N, 400g P, 400g K per tree) along with 50 kg of FYM in the tree basin.",
            "Top Dressing 2 (Post-Monsoon)": "Apply the remaining half dose of chemical fertilizers after the rainy season, during the fruit development period."
        },
        "irrigation_plan": "Basin or drip irrigation is effective. Irrigate at 10-15 day intervals during winter and 5-7 day intervals during summer. Critical stages for irrigation are flowering, fruit set, and fruit development.",
        "pest_disease_management": [
            {"threat": "Citrus Psylla", "solution": "Chemical: Spray with Dimethoate or Imidacloprid during new flushes. Organic: Prune the affected twigs; spray with neem oil."},
            {"threat": "Citrus Canker", "solution": "Chemical: Preventive sprays of Copper Oxychloride (1%) mixed with Streptocycline. Organic: Prune and burn infected branches; use windbreaks to reduce spore spread."}
        ],
        "harvest_indicators": "Fruits are harvested when they attain full size and the characteristic orange color. A simple maturity test is to check the Total Soluble Solids (TSS), which should be above 10-12%."
    },
    "Papaya": {
        "season": "Perennial (short-lived)",
        "soil_prep": "Select a well-drained upland field and dig pits of 50x50x50 cm. Fill the pits with a mixture of topsoil, 10 kg of FYM, 1 kg of neem cake, and 25 g of Carbofuran to manage nematodes.",
        "growth_stages": {
            "Seedling/Establishment (0-3 months)": "Plant seedlings in the center of the pit and provide light, frequent irrigation. Protect from strong winds and frost. Remove extra male plants, keeping 1 male for every 10 female plants.",
            "Vegetative & First Flowering (4-6 months)": "The plant grows rapidly and flowering begins. Start the fertilizer schedule and ensure consistent moisture to prevent flower drop.",
            "Continuous Fruiting/Harvesting (7-24+ months)": "The plant will continuously flower and set fruit. Regular fertilizer application and irrigation are crucial to support the heavy fruit load. Harvesting can begin and continue for up to 2 years."
        },
        "fertilizer_schedule": {
            "Basal Dose (At Planting)": "10 kg FYM + 1 kg Neem Cake per pit.",
            "Top Dressing 1": "Apply 200-250 g of N, P, and K per plant per year. This should be split into 6 doses and applied every two months, starting from the third month of planting.",
            "Top Dressing 2": "Foliar application of micronutrients, especially Boron (0.1%), is important to prevent fruit deformities and improve quality."
        },
        "irrigation_plan": "Papaya requires a lot of water but is extremely sensitive to waterlogging. Use a ring basin system and irrigate every 6-8 days in summer and 10-12 days in winter. Drip irrigation is ideal.",
        "pest_disease_management": [
            {"threat": "Papaya Ring Spot Virus", "solution": "Chemical: No chemical cure. Control the aphid vector by spraying Imidacloprid. Organic: Use resistant varieties; maintain a 'sanitation zone' around the orchard; remove and destroy infected plants immediately."},
            {"threat": "Root Rot (Fungal)", "solution": "Chemical: Drench the soil around the plant with Copper Oxychloride or Metalaxyl. Organic: Ensure excellent drainage; avoid over-watering; apply Trichoderma viride to the soil."}
        ],
        "harvest_indicators": "Harvest fruits when they are fully grown and the skin color turns from dark green to light green with a yellowish tinge at the apical end (the end away from the stalk). The latex of the fruit also turns from milky to watery."
    }
},
CROP_ADVISORY_DB_MELONS_COMMERCIAL = {
    # -----------------------------------------------------------------
    # MELONS
    # -----------------------------------------------------------------
    "Watermelon": {
        "season": "Zaid",
        "soil_prep": "Prepare a well-tilled field by deep plowing 2-3 times to create a fine and loose soil texture. Prepare raised beds or furrows for planting to ensure good drainage and prevent fruit rot.",
        "growth_stages": {
            "Seedling (0-30 days)": "Focus on maintaining optimal moisture for germination and early vine growth. Hand weeding is critical during this stage to prevent competition.",
            "Vegetative/Vine Running (30-60 days)": "The vines grow rapidly and spread. A second dose of nitrogen should be applied, and vines can be trained along the beds to manage space.",
            "Flowering/Fruiting (60-90+ days)": "Pollination is critical; ensure bee activity. Reduce nitrogen and increase potassium application to promote fruit development, sweetness, and size. Be cautious with irrigation to avoid fruit cracking."
        },
        "fertilizer_schedule": {
            "Basal Dose (At Sowing)": "NPK Ratio: 100:60:80 kg/ha. Apply half of N and the full dose of P and K. Organic: Apply 20 tons/ha of well-decomposed FYM.",
            "Top Dressing 1": "Apply 1/4 of Nitrogen 25-30 days after sowing during the early vine development stage.",
            "Top Dressing 2": "Apply the remaining 1/4 of Nitrogen at the time of fruit set, about 50-60 days after sowing."
        },
        "irrigation_plan": "Irrigate in the furrows every 5-7 days. Water stress during flowering and fruit set can cause flower and fruit drop. Stop irrigation 5-7 days before harvesting to increase sugar content (TSS) and improve flavor.",
        "pest_disease_management": [
            {"threat": "Fruit Fly", "solution": "Chemical: Use pheromone traps with cue-lure and spray Malathion. Organic: Bag young developing fruits; use bait traps with jaggery and a few drops of insecticide."},
            {"threat": "Powdery Mildew", "solution": "Chemical: Spray with wettable sulphur or Dinocap. Organic: Spray with a solution of baking soda and water; ensure good air circulation by pruning excess old leaves."}
        ],
        "harvest_indicators": "Harvest when the tendril nearest to the fruit stalk dries up. The belly spot (part of the fruit touching the ground) turns from whitish to creamy yellow, and the fruit produces a dull, hollow sound when thumped."
    },
    "Muskmelon": {
        "season": "Zaid",
        "soil_prep": "The field should be prepared to a fine tilth with 2-3 plowings, followed by planking to make the soil level. Incorporate a good amount of FYM during the last plowing for better soil structure and fertility.",
        "growth_stages": {
            "Seedling (0-30 days)": "Ensure a weed-free environment and consistent moisture for establishment. The plants are sensitive to cold, so protect them from frost in early stages.",
            "Vegetative (30-60 days)": "Vines will spread vigorously. Pinching the terminal shoots can encourage lateral branching, leading to more female flowers and fruits.",
            "Flowering/Fruiting (60-90+ days)": "This stage is critical for pollination. Hand pollination can be done in the morning for better fruit set. Increase potassium application for better fruit quality and net formation on the skin."
        },
        "fertilizer_schedule": {
            "Basal Dose (At Sowing)": "NPK Ratio: 120:80:80 kg/ha. Apply half of N and the full dose of P and K at the time of bed preparation. Organic: 20-25 tons/ha of FYM.",
            "Top Dressing 1": "Apply 1/4 of Nitrogen about 30 days after sowing, when the vines start to run.",
            "Top Dressing 2": "Apply the final 1/4 of Nitrogen at the fruit-setting stage to support development."
        },
        "irrigation_plan": "Irrigate every 4-6 days, preferably in the morning to allow foliage to dry. Avoid over-watering as it can lead to root diseases. Reduce irrigation frequency as fruits start to mature to improve sweetness and aroma.",
        "pest_disease_management": [
            {"threat": "Red Pumpkin Beetle", "solution": "Chemical: Dust Malathion 5% D or spray Carbaryl in the morning hours. Organic: Hand-pick and destroy beetles in the morning; apply wood ash on young plants."},
            {"threat": "Downy Mildew", "solution": "Chemical: Spray with Mancozeb or Ridomil MZ. Organic: Use resistant varieties; avoid overhead irrigation and ensure proper spacing for ventilation."}
        ],
        "harvest_indicators": "The fruit is ready for harvest at the 'full slip' stage, where a gentle twist separates the fruit easily from the vine, leaving a clean scar. The fruit also develops its characteristic musky aroma and the skin color changes."
    },
    # -----------------------------------------------------------------
    # COMMERCIAL/PLANTATION
    # -----------------------------------------------------------------
    "Cotton": {
        "season": "Kharif",
        "soil_prep": "One deep plowing in summer followed by 2-3 harrowings is needed to achieve a deep, well-drained seedbed. Create ridges and furrows for planting to facilitate irrigation and drainage.",
        "growth_stages": {
            "Seedling (0-30 days)": "Ensure proper plant stand through gap filling or thinning. The initial 4-6 weeks are critical for weed control to prevent stunting.",
            "Vegetative (30-75 days)": "This is the 'squaring' or flower bud formation stage. Balanced nutrient application is key. The plant grows rapidly in height and develops branches.",
            "Flowering/Boll Development (75-150+ days)": "This is the most critical phase. The plant flowers, bolls are formed, and they develop and mature. It is highly sensitive to moisture stress and requires intensive pest management, especially against bollworms."
        },
        "fertilizer_schedule": {
            "Basal Dose (At Sowing)": "NPK Ratio: 150:75:75 kg/ha (for irrigated Bt Cotton). Apply 25% of N and the full dose of P and K. Organic: 12.5 tons/ha of FYM.",
            "Top Dressing 1": "Apply 50% of Nitrogen at the squaring stage (around 40-45 days after sowing).",
            "Top Dressing 2": "Apply the remaining 25% of Nitrogen during the peak flowering/boll formation stage (around 75-80 days after sowing)."
        },
        "irrigation_plan": "Irrigate at critical stages: flowering, and boll formation/development. A furrow irrigation every 12-15 days is generally sufficient, depending on soil type. Avoid waterlogging at all stages.",
        "pest_disease_management": [
            {"threat": "Pink Bollworm", "solution": "Chemical: Spray with Profenofos + Cypermethrin combination. Organic: Use pheromone traps for monitoring and mass trapping; destroy crop residues after harvest."},
            {"threat": "Whitefly & Jassids", "solution": "Chemical: Spray with Diafenthiuron or Flonicamid. Organic: Use yellow sticky traps; spray with neem oil or insecticidal soap."}
        ],
        "harvest_indicators": "Harvesting is done in 3-4 pickings as the bolls mature and burst open, exposing the white fluffy cotton. Pick cotton in the morning hours when there is less moisture to ensure good quality."
    },
    "Jute": {
        "season": "Kharif",
        "soil_prep": "The land requires thorough preparation with 2-3 plowings and cross-harrowing to achieve a fine, clean, and soft seedbed. The field must be well-leveled to prevent waterlogging after sowing.",
        "growth_stages": {
            "Seedling (0-30 days)": "This is a critical period for thinning and weeding. Two rounds of thinning and weeding (at 15 and 30 days) are essential to maintain the correct plant population for high-quality fiber.",
            "Vegetative (30-90 days)": "The plants undergo rapid vegetative growth and height gain. This is the main period for fiber development. Ensure adequate nitrogen and moisture.",
            "Flowering/Harvest (90-120 days)": "Harvesting at the small pod stage yields the best quality fiber. Delaying the harvest increases fiber yield but compromises its quality (makes it coarser)."
        },
        "fertilizer_schedule": {
            "Basal Dose (At Sowing)": "NPK Ratio: 60:30:30 kg/ha. Apply the full dose of P and K, and half the dose of N. Organic: 5-7 tons/ha of FYM during land preparation.",
            "Top Dressing 1": "Apply the remaining half dose of Nitrogen 20-25 days after sowing, after the first weeding and thinning.",
            "Top Dressing 2": "Not applicable."
        },
        "irrigation_plan": "Jute is sown during pre-monsoon showers and grows through the monsoon, so it often doesn't require irrigation. However, a pre-sowing irrigation is crucial for germination if rains are delayed.",
        "pest_disease_management": [
            {"threat": "Jute Semilooper", "solution": "Chemical: Spray with Chlorpyrifos or Emamectin Benzoate. Organic: Encourage birds by installing perches; hand-pick and destroy larvae in early stages."},
            {"threat": "Stem Rot", "solution": "Chemical: Seed treatment with Carbendazim and foliar spray if infection occurs. Organic: Practice crop rotation with paddy; ensure good drainage."}
        ],
        "harvest_indicators": "The crop should be harvested when it is in the small pod formation stage, approximately 100-120 days after sowing. The plants are cut close to the ground level."
    },
    "Coconut": {
        "season": "Perennial",
        "soil_prep": "Dig planting pits of 1x1x1 meter size well in advance of the planting season (onset of monsoon). Fill the pit with a mixture of topsoil, 30 kg of well-rotted FYM, and 1 kg of bone meal.",
        "growth_stages": {
            "Establishment (Year 1-3)": "Provide irrigation and shade for the young seedling. Protect from grazing and pests like the rhinoceros beetle. Focus on establishing a healthy root system.",
            "Juvenile/Pre-bearing (Year 4-7)": "The palm grows in height and girth. Continue regular manuring and irrigation. Intercropping with legumes can be practiced to enrich the soil.",
            "Full Bearing (Year 8+)": "The palm produces bunches of nuts regularly. Focus on balanced nutrition, especially potassium, and management of pests like rhinoceros beetle, red palm weevil, and eriophyid mite."
        },
        "fertilizer_schedule": {
            "Basal Dose (At Planting)": "30 kg FYM + 1 kg bone meal per pit.",
            "Top Dressing 1 (Pre-Monsoon - May/June)": "For a mature palm, apply half the annual dose: 25 kg FYM, 250g N, 160g P, and 600g K in a circular basin around the palm.",
            "Top Dressing 2 (Post-Monsoon - Sept/Oct)": "Apply the second half of the chemical fertilizer dose in the basin and incorporate it into the soil."
        },
        "irrigation_plan": "Basin irrigation is common. Irrigate once every 4-5 days during dry summer months. Water requirement is about 600-800 liters per palm per week. Drip irrigation is highly efficient.",
        "pest_disease_management": [
            {"threat": "Rhinoceros Beetle", "solution": "Chemical: Place phorate granules mixed with sand in the innermost leaf axils. Organic: Use pheromone traps (Rhino-lure); hook out the beetle from the crown using a beetle hook."},
            {"threat": "Red Palm Weevil", "solution": "Chemical: Stem injection with Monocrotophos or Imidacloprid. Organic: Use pheromone traps with food bait; avoid causing mechanical injury to the palm trunk."}
        ],
        "harvest_indicators": "Coconuts are harvested every 45-60 days. For tender nuts, harvest at 6-7 months when they are green. For mature nuts (for copra and oil), harvest at 11-12 months when the husk turns brownish and a sloshing sound is heard when shaken."
    },
    "Coffee": {
        "season": "Perennial",
        "soil_prep": "Plant coffee on terraced slopes under the shade of other trees. Dig pits of 50x50x50 cm and fill them with a mixture of topsoil, compost, and rock phosphate before planting.",
        "growth_stages": {
            "Establishment (Year 1-2)": "Plant seedlings at the beginning of the rainy season. Provide shade and protect from pests. Training and centering the plant is done in the second year.",
            "Frame Development (Year 3-4)": "The plant is topped at a desired height (for Arabica) to encourage lateral growth. Pruning is done to maintain the frame and remove unproductive wood.",
            "Full Bearing (Year 5+)": "The plant produces blossoms after spring showers, and berries develop over 8-9 months. Nutrient and shade management are critical. Pruning is done annually after harvest."
        },
        "fertilizer_schedule": {
            "Basal Dose (At Planting)": "Fill the pit with compost and rock phosphate.",
            "Top Dressing 1 (Pre-Blossom - Feb/March)": "Apply a blossom shower dose high in Nitrogen and Phosphorous to encourage healthy blossoms.",
            "Top Dressing 2 (Post-Monsoon - Aug/Sept)": "Apply a backing dose, which is a balanced NPK fertilizer, to support the developing berries and new wood for the next season."
        },
        "irrigation_plan": "Coffee is largely rainfed. However, providing 'blossom showers' through sprinkler irrigation (2.5 cm of water) in Feb-March is critical for uniform flowering if summer rains fail. A second 'backing shower' may be needed 20 days later.",
        "pest_disease_management": [
            {"threat": "Coffee Berry Borer", "solution": "Chemical: Spraying Chlorpyrifos during the berry expansion stage. Organic: Use broca traps; timely and clean harvesting to remove all berries; drying coffee properly."},
            {"threat": "Coffee Leaf Rust", "solution": "Chemical: Prophylactic sprays of Bordeaux mixture before the monsoon and a systemic fungicide like Triadimefon post-monsoon. Organic: Use resistant varieties (e.g., 'Selection' series); maintain optimal shade."}
        ],
        "harvest_indicators": "Harvesting involves selective picking of only the ripe, red berries. This requires multiple rounds of picking over several weeks. The berries should be firm, fully red, and not overripe or dried on the plant."
    }
}