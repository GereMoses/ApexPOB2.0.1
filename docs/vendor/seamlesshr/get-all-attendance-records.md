---
updatedAt: 2025-06-12T22:56:11.000Z
agentTools:
  projectIndex: https://docs.seamlesshr.com/llms.txt
---

# Get Attendance Records

This endpoint can be used to retrieve all attendance records for all employees. You can use the **search** param to filter the records returned by any employee name that matches the keyword supplied. To filter the records by date, the **dateType** parameter needs to be passed. This can be any of these values: **week**, **month**, and **custom**. When the **dateType** is set to **custom**, the **startDate** and **endDate** are required. When the **dateType** is set to **week**, the records returned will be between the start & end of the current week. This also applies to when the **dateType** is set to **month**

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
    "/v1/attendances": {
      "get": {
        "summary": "Get Attendance Records",
        "description": "",
        "operationId": "get-all-attendance-records",
        "parameters": [
          {
            "name": "page",
            "in": "query",
            "description": "This can used to specify the page number of the results to be returned.",
            "schema": {
              "type": "integer",
              "format": "int32",
              "default": 1
            }
          },
          {
            "name": "perPage",
            "in": "query",
            "description": "This can used to specify the number of records to be returned per page e.g 10, 20, 30",
            "schema": {
              "type": "integer",
              "format": "int32",
              "default": 10
            }
          },
          {
            "name": "search",
            "in": "query",
            "description": "This can used to filter the records by an employee name",
            "schema": {
              "type": "string"
            }
          },
          {
            "name": "scheduleType",
            "in": "query",
            "description": "Specifies the type of schedule to filter by. e.g ROTATIONAL or FULLTIME",
            "schema": {
              "type": "string",
              "enum": [
                "ROTATIONAL",
                "FULLTIME"
              ]
            }
          },
          {
            "name": "dateType",
            "in": "query",
            "schema": {
              "type": "string",
              "enum": [
                "week",
                "month",
                "custom"
              ]
            }
          },
          {
            "name": "startDate",
            "in": "query",
            "schema": {
              "type": "string",
              "format": "date"
            }
          },
          {
            "name": "endDate",
            "in": "query",
            "schema": {
              "type": "string",
              "format": "date"
            }
          }
        ],
        "responses": {
          "200": {
            "description": "200",
            "content": {
              "application/json": {
                "examples": {
                  "Result": {
                    "value": "{\n    \"message\": \"Successfully fetched attendance record\",\n    \"data\": [\n        {\n            \"firstName\": \"Adeoye\",\n            \"lastName\": \"Michael\",\n            \"employeeCode\": \"Adeoye\",\n            \"attendanceId\": \"0122\",\n            \"scheduleType\": \"FULLTIME\",\n            \"setClockInDateTime\": \"2024-11-26T09:00:00.000Z\",\n            \"setClockOutDateTime\": \"2024-11-26T17:00:00.000Z\",\n            \"clockInDateTime\": null,\n            \"clockOutDateTime\": null,\n            \"breakStartTime\": null,\n            \"breakEndTime\": null,\n            \"clockInSource\": \"AUTO\",\n            \"clockOutSource\": \"AUTO\",\n            \"punctualityStatus\": \"ABSENT\"\n        },\n        {\n            \"firstName\": \"Michael\",\n            \"lastName\": \"Adeoye\",\n            \"employeeCode\": \"Michael\",\n            \"attendanceId\": \"null\",\n            \"scheduleType\": \"FULLTIME\",\n            \"setClockInDateTime\": \"2024-11-26T09:00:00.000Z\",\n            \"setClockOutDateTime\": \"2024-11-26T16:00:00.000Z\",\n            \"clockInDateTime\": null,\n            \"clockOutDateTime\": null,\n            \"breakStartTime\": null,\n            \"breakEndTime\": null,\n            \"clockInSource\": \"AUTO\",\n            \"clockOutSource\": \"AUTO\",\n            \"punctualityStatus\": \"ABSENT\"\n        },\n        {\n            \"firstName\": \"Adeoye\",\n            \"lastName\": \"Michael\",\n            \"employeeCode\": \"Adeoye\",\n            \"attendanceId\": \"0122\",\n            \"scheduleType\": \"FULLTIME\",\n            \"setClockInDateTime\": \"2024-11-25T09:00:00.000Z\",\n            \"setClockOutDateTime\": \"2024-11-25T17:00:00.000Z\",\n            \"clockInDateTime\": null,\n            \"clockOutDateTime\": null,\n            \"breakStartTime\": null,\n            \"breakEndTime\": null,\n            \"clockInSource\": \"AUTO\",\n            \"clockOutSource\": \"AUTO\",\n            \"punctualityStatus\": \"ABSENT\"\n        },\n        {\n            \"firstName\": \"John\",\n            \"lastName\": \"Doe\",\n            \"employeeCode\": \"EMPLOYEE001\",\n            \"attendanceId\": \"null\",\n            \"scheduleType\": \"FULLTIME\",\n            \"setClockInDateTime\": \"2024-11-25T09:00:00.000Z\",\n            \"setClockOutDateTime\": \"2024-11-25T19:00:00.000Z\",\n            \"clockInDateTime\": \"2024-11-25 12:51:52\",\n            \"clockOutDateTime\": \"2024-11-25 13:08:20\",\n            \"breakStartTime\": null,\n            \"breakEndTime\": null,\n            \"clockInSource\": \"WEB\",\n            \"clockOutSource\": \"WEB\",\n            \"punctualityStatus\": \"ABSENT\"\n        },\n        {\n            \"firstName\": \"John\",\n            \"lastName\": \"Doe\",\n            \"employeeCode\": \"EMPLOYEE001\",\n            \"attendanceId\": \"null\",\n            \"scheduleType\": \"FULLTIME\",\n            \"setClockInDateTime\": \"2024-11-22T09:00:00.000Z\",\n            \"setClockOutDateTime\": \"2024-11-22T15:00:00.000Z\",\n            \"clockInDateTime\": null,\n            \"clockOutDateTime\": null,\n            \"breakStartTime\": null,\n            \"breakEndTime\": null,\n            \"clockInSource\": \"AUTO\",\n            \"clockOutSource\": \"AUTO\",\n            \"punctualityStatus\": \"ABSENT\"\n        },\n        {\n            \"firstName\": \"Adeoye\",\n            \"lastName\": \"Michael\",\n            \"employeeCode\": \"Adeoye\",\n            \"attendanceId\": \"0122\",\n            \"scheduleType\": \"FULLTIME\",\n            \"setClockInDateTime\": \"2024-11-22T09:00:00.000Z\",\n            \"setClockOutDateTime\": \"2024-11-22T17:00:00.000Z\",\n            \"clockInDateTime\": null,\n            \"clockOutDateTime\": null,\n            \"breakStartTime\": null,\n            \"breakEndTime\": null,\n            \"clockInSource\": \"AUTO\",\n            \"clockOutSource\": \"AUTO\",\n            \"punctualityStatus\": \"ABSENT\"\n        },\n        {\n            \"firstName\": \"Adeoye\",\n            \"lastName\": \"Michael\",\n            \"employeeCode\": \"Adeoye\",\n            \"attendanceId\": \"0122\",\n            \"scheduleType\": \"FULLTIME\",\n            \"setClockInDateTime\": \"2024-11-21T09:00:00.000Z\",\n            \"setClockOutDateTime\": \"2024-11-21T17:00:00.000Z\",\n            \"clockInDateTime\": null,\n            \"clockOutDateTime\": null,\n            \"breakStartTime\": null,\n            \"breakEndTime\": null,\n            \"clockInSource\": \"AUTO\",\n            \"clockOutSource\": \"AUTO\",\n            \"punctualityStatus\": \"ABSENT\"\n        },\n        {\n            \"firstName\": \"John\",\n            \"lastName\": \"Doe\",\n            \"employeeCode\": \"EMPLOYEE001\",\n            \"attendanceId\": \"null\",\n            \"scheduleType\": \"FULLTIME\",\n            \"setClockInDateTime\": \"2024-11-21T09:00:00.000Z\",\n            \"setClockOutDateTime\": \"2024-11-21T19:00:00.000Z\",\n            \"clockInDateTime\": \"2024-11-21 10:13:51\",\n            \"clockOutDateTime\": \"2024-11-21 19:00:00\",\n            \"breakStartTime\": null,\n            \"breakEndTime\": null,\n            \"clockInSource\": \"WEB\",\n            \"clockOutSource\": \"AUTO\",\n            \"punctualityStatus\": \"ABSENT\"\n        },\n        {\n            \"firstName\": \"John\",\n            \"lastName\": \"Doe\",\n            \"employeeCode\": \"EMPLOYEE001\",\n            \"attendanceId\": \"null\",\n            \"scheduleType\": \"FULLTIME\",\n            \"setClockInDateTime\": \"2024-11-20T09:00:00.000Z\",\n            \"setClockOutDateTime\": \"2024-11-20T19:00:00.000Z\",\n            \"clockInDateTime\": \"2024-11-20 09:43:05\",\n            \"clockOutDateTime\": \"2024-11-20 19:00:00\",\n            \"breakStartTime\": null,\n            \"breakEndTime\": null,\n            \"clockInSource\": \"WEB\",\n            \"clockOutSource\": \"AUTO\",\n            \"punctualityStatus\": \"LATE\"\n        },\n        {\n            \"firstName\": \"Adeoye\",\n            \"lastName\": \"Michael\",\n            \"employeeCode\": \"Adeoye\",\n            \"attendanceId\": \"0122\",\n            \"scheduleType\": \"FULLTIME\",\n            \"setClockInDateTime\": \"2024-11-19T09:00:00.000Z\",\n            \"setClockOutDateTime\": \"2024-11-19T17:00:00.000Z\",\n            \"clockInDateTime\": null,\n            \"clockOutDateTime\": null,\n            \"breakStartTime\": null,\n            \"breakEndTime\": null,\n            \"clockInSource\": \"AUTO\",\n            \"clockOutSource\": \"AUTO\",\n            \"punctualityStatus\": \"ABSENT\"\n        },\n        {\n            \"firstName\": \"Adeoye\",\n            \"lastName\": \"Michael\",\n            \"employeeCode\": \"Adeoye\",\n            \"attendanceId\": \"0122\",\n            \"scheduleType\": \"FULLTIME\",\n            \"setClockInDateTime\": \"2024-11-20T09:00:00.000Z\",\n            \"setClockOutDateTime\": \"2024-11-20T17:00:00.000Z\",\n            \"clockInDateTime\": null,\n            \"clockOutDateTime\": null,\n            \"breakStartTime\": null,\n            \"breakEndTime\": null,\n            \"clockInSource\": \"AUTO\",\n            \"clockOutSource\": \"AUTO\",\n            \"punctualityStatus\": \"ABSENT\"\n        },\n        {\n            \"firstName\": \"Michael\",\n            \"lastName\": \"Adeoye\",\n            \"employeeCode\": \"Michael\",\n            \"attendanceId\": \"null\",\n            \"scheduleType\": \"FULLTIME\",\n            \"setClockInDateTime\": \"2024-11-19T09:00:00.000Z\",\n            \"setClockOutDateTime\": \"2024-11-19T17:00:00.000Z\",\n            \"clockInDateTime\": \"2024-11-19 10:03:39\",\n            \"clockOutDateTime\": \"2024-11-19 17:00:00\",\n            \"breakStartTime\": null,\n            \"breakEndTime\": null,\n            \"clockInSource\": \"WEB\",\n            \"clockOutSource\": \"AUTO\",\n            \"punctualityStatus\": \"ABSENT\"\n        },\n        {\n            \"firstName\": \"Nkechi\",\n            \"lastName\": \"Onyimadu\",\n            \"employeeCode\": \"Nkechi\",\n            \"attendanceId\": \"null\",\n            \"scheduleType\": \"FULLTIME\",\n            \"setClockInDateTime\": \"2024-11-18T09:00:00.000Z\",\n            \"setClockOutDateTime\": \"2024-11-18T18:00:00.000Z\",\n            \"clockInDateTime\": null,\n            \"clockOutDateTime\": null,\n            \"breakStartTime\": null,\n            \"breakEndTime\": null,\n            \"clockInSource\": \"AUTO\",\n            \"clockOutSource\": \"AUTO\",\n            \"punctualityStatus\": \"ABSENT\"\n        },\n        {\n            \"firstName\": \"Nathaniel\",\n            \"lastName\": \"Babalola\",\n            \"employeeCode\": \"Nathaniel\",\n            \"attendanceId\": \"null\",\n            \"scheduleType\": \"FULLTIME\",\n            \"setClockInDateTime\": \"2024-11-18T09:00:00.000Z\",\n            \"setClockOutDateTime\": \"2024-11-18T18:00:00.000Z\",\n            \"clockInDateTime\": null,\n            \"clockOutDateTime\": null,\n            \"breakStartTime\": null,\n            \"breakEndTime\": null,\n            \"clockInSource\": \"AUTO\",\n            \"clockOutSource\": \"AUTO\",\n            \"punctualityStatus\": \"ABSENT\"\n        },\n        {\n            \"firstName\": \"Onwugbenu\",\n            \"lastName\": \"Chisom\",\n            \"employeeCode\": \"Onwugbenu\",\n            \"attendanceId\": \"null\",\n            \"scheduleType\": \"FULLTIME\",\n            \"setClockInDateTime\": \"2024-11-18T09:00:00.000Z\",\n            \"setClockOutDateTime\": \"2024-11-18T17:00:00.000Z\",\n            \"clockInDateTime\": null,\n            \"clockOutDateTime\": null,\n            \"breakStartTime\": null,\n            \"breakEndTime\": null,\n            \"clockInSource\": \"AUTO\",\n            \"clockOutSource\": \"AUTO\",\n            \"punctualityStatus\": \"ABSENT\"\n        },\n        {\n            \"firstName\": \"Babalola\",\n            \"lastName\": \"Nathaniel\",\n            \"employeeCode\": \"Babalola\",\n            \"attendanceId\": \"null\",\n            \"scheduleType\": \"FULLTIME\",\n            \"setClockInDateTime\": \"2024-11-18T09:00:00.000Z\",\n            \"setClockOutDateTime\": \"2024-11-18T17:00:00.000Z\",\n            \"clockInDateTime\": null,\n            \"clockOutDateTime\": null,\n            \"breakStartTime\": null,\n            \"breakEndTime\": null,\n            \"clockInSource\": \"AUTO\",\n            \"clockOutSource\": \"AUTO\",\n            \"punctualityStatus\": \"ABSENT\"\n        },\n        {\n            \"firstName\": \"Nathaniel\",\n            \"lastName\": \"Babalola\",\n            \"employeeCode\": \"Nathaniel\",\n            \"attendanceId\": \"null\",\n            \"scheduleType\": \"FULLTIME\",\n            \"setClockInDateTime\": \"2024-11-18T09:00:00.000Z\",\n            \"setClockOutDateTime\": \"2024-11-18T17:00:00.000Z\",\n            \"clockInDateTime\": null,\n            \"clockOutDateTime\": null,\n            \"breakStartTime\": null,\n            \"breakEndTime\": null,\n            \"clockInSource\": \"AUTO\",\n            \"clockOutSource\": \"AUTO\",\n            \"punctualityStatus\": \"ABSENT\"\n        },\n        {\n            \"firstName\": \"Adeoye\",\n            \"lastName\": \"Michael\",\n            \"employeeCode\": \"Adeoye\",\n            \"attendanceId\": \"0122\",\n            \"scheduleType\": \"FULLTIME\",\n            \"setClockInDateTime\": \"2024-11-18T09:00:00.000Z\",\n            \"setClockOutDateTime\": \"2024-11-18T17:00:00.000Z\",\n            \"clockInDateTime\": null,\n            \"clockOutDateTime\": null,\n            \"breakStartTime\": null,\n            \"breakEndTime\": null,\n            \"clockInSource\": \"AUTO\",\n            \"clockOutSource\": \"AUTO\",\n            \"punctualityStatus\": \"ABSENT\"\n        },\n        {\n            \"firstName\": \"Nkechi\",\n            \"lastName\": \"Onyimadu\",\n            \"employeeCode\": \"Nkechi\",\n            \"attendanceId\": \"null\",\n            \"scheduleType\": \"FULLTIME\",\n            \"setClockInDateTime\": \"2024-11-18T09:00:00.000Z\",\n            \"setClockOutDateTime\": \"2024-11-18T17:00:00.000Z\",\n            \"clockInDateTime\": null,\n            \"clockOutDateTime\": null,\n            \"breakStartTime\": null,\n            \"breakEndTime\": null,\n            \"clockInSource\": \"AUTO\",\n            \"clockOutSource\": \"AUTO\",\n            \"punctualityStatus\": \"ABSENT\"\n        },\n        {\n            \"firstName\": \"Michael\",\n            \"lastName\": \"Adeoye\",\n            \"employeeCode\": \"Michael\",\n            \"attendanceId\": \"null\",\n            \"scheduleType\": \"FULLTIME\",\n            \"setClockInDateTime\": \"2024-11-18T09:00:00.000Z\",\n            \"setClockOutDateTime\": \"2024-11-18T17:00:00.000Z\",\n            \"clockInDateTime\": \"2024-11-18 11:59:43\",\n            \"clockOutDateTime\": \"2024-11-18 11:59:51\",\n            \"breakStartTime\": null,\n            \"breakEndTime\": null,\n            \"clockInSource\": \"MOBILE\",\n            \"clockOutSource\": \"MOBILE\",\n            \"punctualityStatus\": \"ABSENT\"\n        }\n    ],\n    \"meta\": {\n        \"from\": 1,\n        \"to\": 20,\n        \"total\": 3782\n    }\n}"
                  }
                },
                "schema": {
                  "type": "object",
                  "properties": {
                    "message": {
                      "type": "string",
                      "example": "Successfully fetched attendance record"
                    },
                    "data": {
                      "type": "array",
                      "items": {
                        "type": "object",
                        "properties": {
                          "firstName": {
                            "type": "string",
                            "example": "Adeoye"
                          },
                          "lastName": {
                            "type": "string",
                            "example": "Michael"
                          },
                          "employeeCode": {
                            "type": "string",
                            "example": "Adeoye"
                          },
                          "attendanceId": {
                            "type": "string",
                            "example": "0122"
                          },
                          "scheduleType": {
                            "type": "string",
                            "example": "FULLTIME"
                          },
                          "setClockInDateTime": {
                            "type": "string",
                            "example": "2024-11-26T09:00:00.000Z"
                          },
                          "setClockOutDateTime": {
                            "type": "string",
                            "example": "2024-11-26T17:00:00.000Z"
                          },
                          "clockInDateTime": {},
                          "clockOutDateTime": {},
                          "breakStartTime": {},
                          "breakEndTime": {},
                          "clockInSource": {
                            "type": "string",
                            "example": "AUTO"
                          },
                          "clockOutSource": {
                            "type": "string",
                            "example": "AUTO"
                          },
                          "punctualityStatus": {
                            "type": "string",
                            "example": "ABSENT"
                          }
                        }
                      }
                    },
                    "meta": {
                      "type": "object",
                      "properties": {
                        "from": {
                          "type": "integer",
                          "example": 1,
                          "default": 0
                        },
                        "to": {
                          "type": "integer",
                          "example": 20,
                          "default": 0
                        },
                        "total": {
                          "type": "integer",
                          "example": 3782,
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