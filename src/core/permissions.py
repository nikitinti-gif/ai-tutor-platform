from src.core.roles import *

PERMISSIONS = {

    ROLE_STUDENT: [

        "view_homework",

        "upload_photo",

        "view_progress",

        "ask_ai"

    ],

    ROLE_PARENT: [

        "view_reports",

        "view_progress"

    ],

    ROLE_TEACHER: [

        "manage_students",

        "create_homework",

        "review_ai",

        "analytics"

    ]
}