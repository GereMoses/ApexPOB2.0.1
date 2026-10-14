---
updatedAt: 2025-06-12T22:55:07.000Z
agentTools:
  projectIndex: https://docs.seamlesshr.com/llms.txt
---

# Get All Employees

This endpoint is suitable for getting the basic information of all employees within your organization. Also, you can filter the results returned by this endpoint by passing **date**, **status**, and **limit** as part of the request parameters.

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
    "/v1/employees": {
      "get": {
        "summary": "Get All Employees",
        "description": "",
        "operationId": "fetch-employees",
        "parameters": [
          {
            "name": "company",
            "in": "query",
            "description": "This field is optional. If not passed, the records returned will be for the holding company.",
            "schema": {
              "type": "string"
            }
          },
          {
            "name": "date",
            "in": "query",
            "description": "filter by date employee was created",
            "schema": {
              "type": "string",
              "format": "date"
            }
          },
          {
            "name": "limit",
            "in": "query",
            "description": "limit records",
            "schema": {
              "type": "integer",
              "format": "int32",
              "default": 10
            }
          },
          {
            "name": "status",
            "in": "query",
            "description": "filter by status of employees active or inactive",
            "schema": {
              "type": "string"
            }
          },
          {
            "name": "can_login",
            "in": "query",
            "description": "filter by employees that can login to the system.",
            "schema": {
              "type": "boolean"
            }
          },
          {
            "name": "employment_date[]",
            "in": "query",
            "description": "filter by employment date of employees e.g ['2025-02-01', '2025-03-31']",
            "schema": {
              "type": "string"
            }
          },
          {
            "name": "exit_status",
            "in": "query",
            "description": "filter employees record by exit status",
            "schema": {
              "type": "boolean"
            }
          },
          {
            "name": "exit_date[]",
            "in": "query",
            "description": "filter the employees record by exit date e.g e.g ['2025-02-01', '2025-03-31']",
            "schema": {
              "type": "string"
            }
          },
          {
            "in": "query",
            "name": "page",
            "schema": {
              "type": "integer",
              "default": "1"
            },
            "description": "filter records based on page number"
          },
          {
            "in": "query",
            "name": "q",
            "schema": {
              "type": "string"
            },
            "description": "This can be used to search for employees where the character matches. It searches the following fields: firstname, lastname, employee_code, and email.",
            "required": false
          }
        ],
        "responses": {
          "200": {
            "description": "200",
            "content": {
              "application/json": {
                "examples": {
                  "Result": {
                    "value": "{\n  \"status\": 200,\n  \"message\": \"\",\n  \"data\": [\n    {\n        \"staff_id\": \"EMPLOYEE001\",\n        \"sup_id\": null,\n        \"staff_name\": \"John Doe\",\n        \"staff_other_names\": null,\n        \"staff_email\": \"johndoe@gmail.com\",\n        \"staff_phone\": null,\n        \"personal_email_address\": null,\n        \"staff_image_url\": \"https://johnyy.seamlesshrms.com/img/dp.png\",\n        \"confirmation_status\": \"Confirmed\",\n        \"confirmation_date\": null,\n        \"date_of_birth\": null,\n        \"age\": null,\n        \"sex\": null,\n        \"marital_status\": null,\n        \"employment_date\": null,\n        \"length_of_service\": null,\n        \"last_promotion\": null,\n        \"department\": null,\n        \"unit\": null,\n        \"job_title\": null,\n        \"paygroup\": null,\n        \"grade\": null,\n        \"line_manager\": null,\n        \"branches\": null,\n        \"cost_centre\": null,\n        \"regions\": null,\n        \"state_deployed\": null,\n        \"state_of_origin\": null,\n        \"religion\": null,\n        \"bank_name\": null,\n        \"account_number\": null,\n        \"residential_address\": null,\n        \"permanent_address\": null,\n        \"pension_details\": null,\n        \"pin_numbers\": null,\n        \"qualifications\": [],\n        \"next_of_kin\": [],\n        \"experience\": [],\n        \"gross_salary\": null,\n        \"contract_type\": null,\n        \"contract_start_date\": null,\n        \"tenure_on_grade\": null,\n        \"net_salary\": 0,\n        \"loan_balance\": 0,\n        \"exit_status\": false,\n        \"entity\": \"Johny PLC\"\n    },\n    {\n        \"staff_id\": \"EMPLOYEE002\",\n        \"sup_id\": null,\n        \"staff_name\": \"Jane Done\",\n        \"staff_other_names\": null,\n        \"staff_email\": \"example02@gmail.com\",\n        \"staff_phone\": null,\n        \"personal_email_address\": null,\n        \"staff_image_url\": \"https://johnyy.seamlesshrms.com/img/dp.png\",\n        \"confirmation_status\": \"Confirmed\",\n        \"confirmation_date\": null,\n        \"date_of_birth\": null,\n        \"age\": null,\n        \"sex\": null,\n        \"marital_status\": null,\n        \"employment_date\": null,\n        \"length_of_service\": null,\n        \"last_promotion\": null,\n        \"department\": null,\n        \"unit\": null,\n        \"job_title\": null,\n        \"paygroup\": null,\n        \"grade\": null,\n        \"line_manager\": null,\n        \"line_manager_email_address\": null,\n        \"branches\": null,\n        \"cost_centre\": null,\n        \"regions\": null,\n        \"state_deployed\": null,\n        \"state_of_origin\": null,\n        \"religion\": null,\n        \"bank_name\": null,\n        \"account_number\": null,\n        \"residential_address\": null,\n        \"permanent_address\": null,\n        \"pension_details\": null,\n        \"pin_numbers\": null,\n        \"qualifications\": [],\n        \"next_of_kin\": [],\n        \"experience\": [],\n        \"gross_salary\": null,\n        \"contract_type\": null,\n        \"contract_start_date\": null,\n        \"tenure_on_grade\": null,\n        \"net_salary\": 0,\n        \"loan_balance\": 0,\n        \"exit_status\": false,\n        \"entity\": \"Johny PLC\"\n    }\n]\n}"
                  }
                },
                "schema": {
                  "type": "object",
                  "properties": {
                    "status": {
                      "type": "integer",
                      "example": 200,
                      "default": 0
                    },
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
                            "example": "EMPLOYEE001"
                          },
                          "sup_id": {},
                          "staff_name": {
                            "type": "string",
                            "example": "John Doe"
                          },
                          "staff_other_names": {},
                          "staff_email": {
                            "type": "string",
                            "example": "johndoe@gmail.com"
                          },
                          "staff_phone": {},
                          "personal_email_address": {},
                          "staff_image_url": {
                            "type": "string",
                            "example": "https://johnyy.seamlesshrms.com/img/dp.png"
                          },
                          "confirmation_status": {
                            "type": "string",
                            "example": "Confirmed"
                          },
                          "confirmation_date": {},
                          "date_of_birth": {},
                          "age": {},
                          "sex": {},
                          "marital_status": {},
                          "employment_date": {},
                          "length_of_service": {},
                          "last_promotion": {},
                          "department": {},
                          "unit": {},
                          "job_title": {},
                          "paygroup": {},
                          "grade": {},
                          "line_manager": {},
                          "branches": {},
                          "cost_centre": {},
                          "regions": {},
                          "state_deployed": {},
                          "state_of_origin": {},
                          "religion": {},
                          "bank_name": {},
                          "account_number": {},
                          "residential_address": {},
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
                            "example": false,
                            "default": true
                          },
                          "entity": {
                            "type": "string",
                            "example": "Johny PLC"
                          }
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