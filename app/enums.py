# All user-facing values are French.

DEFAULT_CATEGORIES = [
    "Frigo",
    "Congélateur",
    "Fruits & légumes",
    "Épicerie / Sec",
    "Épices & condiments",
    "Huiles & vinaigres",
    "Autre",
]

# Items added under these categories default to is_staple=True.
STAPLE_CATEGORIES = ["Épices & condiments", "Huiles & vinaigres"]

DEFAULT_STORE_TYPES = [
    "Boucherie",
    "Poissonnerie",
    "Primeur",
    "Boulangerie",
    "Fromagerie",
    "Épicerie / Supermarché",
    "Autre",
]

DEFAULT_TOOLS = [
    "Four", "Plaques de cuisson", "Micro-ondes", "Mixeur / blender",
    "Robot pâtissier", "Air fryer", "Cocotte / faitout", "Poêle anti-adhésive",
    "Autocuiseur", "Wok", "Balance de cuisine", "Thermomètre de cuisson",
]

DEFAULT_SKILLS = [
    "Découpe au couteau", "Pâte / pâtisserie", "Cuisson des viandes",
    "Émulsions / sauces", "Cuisson du poisson", "Fermentation",
]

SLOTS = ["dejeuner", "diner"]  # internal keys; labels via i18n
