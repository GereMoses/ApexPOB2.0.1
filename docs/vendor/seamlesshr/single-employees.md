---
updatedAt: 2025-06-12T22:55:10.000Z
agentTools:
  projectIndex: https://docs.seamlesshr.com/llms.txt
---

# Get Single Employee

This endpoint is suitable for getting the details of a particular employee. This can be achieved by passing the **staff\_id** of the employee as a path parameter to the endpoint.

# OpenAPI definition

```json
{
  "openapi": "3.1.0",
  "info": {
    "title": "seamless-hr-apis",
    "version": "1.0"
  },
  "servers": [
    {
      "url": "https://api-sandbox.seamlesshr.app"
    }
  ],
  "components": {
    "securitySchemes": {
      "sec0": {
        "type": "apiKey",
        "in": "header",
        "name": "x-client-secret",
        "x-default": ""
      },
      "sec1": {
        "type": "apiKey",
        "in": "header",
        "name": "x-client-id"
      }
    }
  },
  "security": [
    {
      "sec0": [],
      "sec1": []
    }
  ],
  "paths": {
    "/v1/employees/{staff_id}": {
      "get": {
        "summary": "Get Single Employee",
        "description": "",
        "operationId": "single-employees",
        "parameters": [
          {
            "name": "staff_id",
            "in": "path",
            "schema": {
              "type": "string"
            },
            "required": true
          }
        ],
        "responses": {
          "200": {
            "description": "200",
            "content": {
              "application/json": {
                "examples": {
                  "Result": {
                    "value": "{\n    \"message\": \"\",\n    \"data\": [\n        {\n            \"staff_id\": \"employee001\",\n            \"sup_id\": null,\n            \"staff_name\": \"John DOe\",\n            \"staff_other_names\": null,\n            \"staff_email\": \"johndoe@gmail.com\",\n            \"staff_phone\": \"000871311252\",\n            \"personal_email_address\": null,\n            \"staff_image_url\": \"\",\n            \"confirmation_status\": \"Confirmed\",\n            \"confirmation_date\": null,\n            \"date_of_birth\": \"15/06/1980\",\n            \"age\": \"43 years 11 months\",\n            \"sex\": \"Male\",\n            \"marital_status\": \"Married\",\n            \"employment_date\": \"2015-08-09T23:00:00.000000Z\",\n            \"length_of_service\": \"8 years 9 months\",\n            \"last_promotion\": null,\n            \"department\": null,\n            \"unit\": null,\n            \"job_title\": null,\n            \"paygroup\": null,\n            \"grade\": null,\n            \"line_manager\": null,\n            \"line_manager_email_address\": null,\n            \"branches\": null,\n            \"cost_centre\": null,\n            \"regions\": null,\n            \"state_deployed\": null,\n            \"state_of_origin\": \"Lagos\",\n            \"religion\": null,\n            \"bank_name\": \"Nigearia\",\n            \"account_number\": \"1053202\",\n            \"residential_address\": \" \",\n            \"permanent_address\": null,\n            \"pension_details\": null,\n            \"pin_numbers\": null,\n            \"qualifications\": [],\n            \"next_of_kin\": [],\n            \"experience\": [],\n            \"gross_salary\": null,\n            \"contract_type\": null,\n            \"contract_start_date\": null,\n            \"tenure_on_grade\": null,\n            \"net_salary\": 0,\n            \"loan_balance\": 0,\n            \"exit_status\": true,\n            \"exit_date\": \"2024-03-31\",\n            \"entity\": \"My company\",\n            \"exit_mode\": \"VOLUNTARY RESIGNATION\",\n            \"exit_reason\": \"Better opportunities\",\n            \"exit_remark\": null\n        }\n    ],\n    \"meta\": {\n        \"current_page\": 1,\n        \"last_page\": 1,\n        \"per_page\": 10,\n        \"total\": 1\n    }\n}"
                  }
                },
                "schema": {
                  "type": "object",
                  "properties": {
                    "message": {
                      "type": "string",
                      "example": ""
                    },
                    "data": {
                      "type": "array",
                      "items": {
                        "type": "object",
                        "properties": {
                          "staff_id": {
                            "type": "string",
                            "example": "employee001"
                          },
                          "sup_id": {},
                          "staff_name": {
                            "type": "string",
                            "example": "John DOe"
                          },
                          "staff_other_names": {},
                          "staff_email": {
                            "type": "string",
                            "example": "johndoe@gmail.com"
                          },
                          "staff_phone": {
                            "type": "string",
                            "example": "000871311252"
                          },
                          "personal_email_address": {},
                          "staff_image_url": {
                            "type": "string",
                            "example": ""
                          },
                          "confirmation_status": {
                            "type": "string",
                            "example": "Confirmed"
                          },
                          "confirmation_date": {},
                          "date_of_birth": {
                            "type": "string",
                            "example": "15/06/1980"
                          },
                          "age": {
                            "type": "string",
                            "example": "43 years 11 months"
                          },
                          "sex": {
                            "type": "string",
                            "example": "Male"
                          },
                          "marital_status": {
                            "type": "string",
                            "example": "Married"
                          },
                          "employment_date": {
                            "type": "string",
                            "example": "2015-08-09T23:00:00.000000Z"
                          },
                          "length_of_service": {
                            "type": "string",
                            "example": "8 years 9 months"
                          },
                          "last_promotion": {},
                          "department": {},
                          "unit": {},
                          "job_title": {},
                          "paygroup": {},
                          "grade": {},
                          "line_manager": {},
                          "line_manager_email_address": {},
                          "branches": {},
                          "cost_centre": {},
                          "regions": {},
                          "state_deployed": {},
                          "state_of_origin": {
                            "type": "string",
                            "example": "Lagos"
                          },
                          "religion": {},
                          "bank_name": {
                            "type": "string",
                            "example": "Nigearia"
                          },
                          "account_number": {
                            "type": "string",
                            "example": "1053202"
                          },
                          "residential_address": {
                            "type": "string",
                            "example": " "
                          },
                          "permanent_address": {},
                          "pension_details": {},
                          "pin_numbers": {},
                          "qualifications": {
                            "type": "array"
                          },
                          "next_of_kin": {
                            "type": "array"
                          },
                          "experience": {
                            "type": "array"
                          },
                          "gross_salary": {},
                          "contract_type": {},
                          "contract_start_date": {},
                          "tenure_on_grade": {},
                          "net_salary": {
                            "type": "integer",
                            "example": 0,
                            "default": 0
                          },
                          "loan_balance": {
                            "type": "integer",
                            "example": 0,
                            "default": 0
                          },
                          "exit_status": {
                            "type": "boolean",
                            "example": true,
                            "default": true
                          },
                          "exit_date": {
                            "type": "string",
                            "example": "2024-03-31"
                          },
                          "entity": {
                            "type": "string",
                            "example": "My company"
                          },
                          "exit_mode": {
                            "type": "string",
                            "example": "VOLUNTARY RESIGNATION"
                          },
                          "exit_reason": {
                            "type": "string",
                            "example": "Better opportunities"
                          },
                          "exit_remark": {}
                        }
                      }
                    },
                    "meta": {
                      "type": "object",
                      "properties": {
                        "current_page": {
                          "type": "integer",
                          "example": 1,
                          "default": 0
                        },
                        "last_page": {
                          "type": "integer",
                          "example": 1,
                          "default": 0
                        },
                        "per_page": {
                          "type": "integer",
                          "example": 10,
                          "default": 0
                        },
                        "total": {
                          "type": "integer",
                          "example": 1,
                          "default": 0
                        }
                      }
                    }
                  }
                }
              }
            }
          },
          "400": {
            "description": "400",
            "content": {
              "application/json": {
                "examples": {
                  "Result": {
                    "value": "{}"
                  }
                },
                "schema": {
                  "type": "object",
                  "properties": {}
                }
              }
            }
          }
        },
        "deprecated": false
      }
    }
  },
  "x-readme": {
    "headers": [],
    "explorer-enabled": true,
    "proxy-enabled": true
  },
  "x-readme-fauxas": true
}
```