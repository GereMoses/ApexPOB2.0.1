---
updatedAt: 2025-11-03T11:37:50.000Z
agentTools:
  projectIndex: https://docs.seamlesshr.com/llms.txt
---

# Bulk Sync Attendance Records

This endpoint allows biometric devices to securely transmit bulk attendance data to the Time & Attendance (T\&A) module for synchronization and record-keeping. It supports real-time and accurate tracking of employee attendance across all devices, with a maximum limit of 100 records per request.

<br />

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
    "/biometric/process": {
      "post": {
        "description": "",
        "operationId": "post_biometricprocess-1",
        "responses": {
          "200": {
            "description": "",
            "content": {
              "application/json": {
                "examples": {
                  "New Example": {
                    "summary": "New Example",
                    "value": ""
                  },
                  "Success": {
                    "summary": "Success",
                    "value": {
                      "message": "Attendance data sent successfully",
                      "data": {
                        "data": "OK",
                        "message": "Attendance data synced successfully"
                      }
                    }
                  }
                }
              }
            }
          },
          "400": {
            "description": "Bad Request",
            "content": {
              "application/json": {
                "examples": {
                  "Bad Request": {
                    "value": {
                      "message": "Unable to process records"
                    },
                    "summary": "Bad Request"
                  }
                }
              }
            }
          },
          "422": {
            "description": "Unprocessable Entity",
            "content": {
              "application/json": {
                "examples": {
                  "Validation Error": {
                    "value": {
                      "message": "Validation error",
                      "errors": {
                        "attendanceId": [
                          "Attendance ID is required"
                        ],
                        "dateTime": [
                          "dateTime must be a valid ISO 8601 date string"
                        ],
                        "type": [
                          "Type is required"
                        ],
                        "deviceSN": [
                          "Device serial number is required"
                        ]
                      }
                    },
                    "summary": "Validation Error"
                  }
                }
              }
            }
          }
        },
        "parameters": [],
        "requestBody": {
          "content": {
            "application/json": {
              "schema": {
                "type": "array",
                "items": {
                  "properties": {
                    "attendanceId": {
                      "type": "string",
                      "description": "Unique ID for the attendance record.",
                      "default": "1010101"
                    },
                    "dateTime": {
                      "type": "string",
                      "format": "date-time",
                      "description": "Exact date and time of the attendance event(ISO 8601 date string)",
                      "default": "2025-07-16T08:44:16+00:00"
                    },
                    "type": {
                      "type": "string",
                      "description": "Type of event",
                      "default": "CLOCK_IN"
                    },
                    "deviceSN": {
                      "type": "string",
                      "description": "Serial number of the biometric device",
                      "default": "84785894944"
                    }
                  },
                  "type": "object",
                  "required": [
                    "attendanceId",
                    "dateTime",
                    "type",
                    "deviceSN"
                  ]
                }
              }
            }
          }
        },
        "x-readme": {
          "code-samples": [
            {
              "code": "curl -X POST https://api-sandbox.seamlesshr.app/biometric/process \\\n  -H \"Content-Type: application/json\" \\\n  -d '[{\n    \"attendanceId\": \"2342\",\n    \"dateTime\": \"2025-07-07T13:45:30\",\n    \"type\": \"sm\",\n    \"deviceSN\": \"344\"\n  }]'\n",
              "language": "shell",
              "name": ""
            },
            {
              "code": "const payload = {\n  attendanceId: \"2342\",\n  dateTime: \"2025-07-07T13:45:30\",\n  type: \"sm\",\n  deviceSN: \"344\"\n};\n\nfetch('https://api-sandbox.seamlesshr.app/biometric/process', {\n  method: 'POST',\n  headers: { 'Content-Type': 'application/json' },\n  body: JSON.stringify(payload)\n})\n  .then(res => res.json())\n  .then(data => console.log('✅ Success:', data))\n  .catch(err => console.error('❌ Error:', err));\n",
              "language": "javascript",
              "name": ""
            },
            {
              "code": "<?php\n\nrequire 'vendor/autoload.php'; // Make sure you installed Guzzle with `composer require guzzlehttp/guzzle`\n\nuse GuzzleHttp\\Client;\nuse GuzzleHttp\\Exception\\RequestException;\n\n$client = new Client([\n    'base_uri' => 'https://api-sandbox.seamlesshr.app',\n    'timeout'  => 10.0,\n]);\n\ntry {\n    $response = $client->post('/biometric/process', [\n        'headers' => [\n            'Content-Type' => 'application/json',\n        ],\n        'json' => [\n            'attendanceId' => '2342',\n            'dateTime'     => '2025-07-07T13:45:30',\n            'type'         => 'sm',\n            'deviceSN'     => '344',\n        ]\n    ]);\n\n    $statusCode = $response->getStatusCode();\n    $body = $response->getBody()->getContents();\n\n    echo \"✅ HTTP $statusCode\\n\";\n    echo \"Response: $body\\n\";\n\n} catch (RequestException $e) {\n    if ($e->hasResponse()) {\n        echo \"❌ HTTP \" . $e->getResponse()->getStatusCode() . \"\\n\";\n        echo $e->getResponse()->getBody()->getContents();\n    } else {\n        echo \"❌ Request failed: \" . $e->getMessage();\n    }\n}\n",
              "language": "php",
              "name": ""
            },
            {
              "code": "import requests\nimport json\n\nurl = \"https://api-sandbox.seamlesshr.app/biometric/process\"\n\npayload = {\n    \"attendanceId\": \"2342\",\n    \"dateTime\": \"2025-07-07T13:45:30\",\n    \"type\": \"sm\",\n    \"deviceSN\": \"344\"\n}\n\nheaders = {\n    \"Content-Type\": \"application/json\",\n}\n\ntry:\n    response = requests.post(url, headers=headers, json=payload)\n    response.raise_for_status()  # Raise an error on bad status\n\n    print(f\"✅ HTTP {response.status_code}\")\n    print(\"Response:\", json.dumps(response.json(), indent=2))\n\nexcept requests.exceptions.HTTPError as http_err:\n    print(f\"❌ HTTP error: {http_err}\")\n    if response.content:\n        print(\"Response:\", response.content.decode())\n\nexcept Exception as err:\n    print(f\"❌ Other error: {err}\")\n",
              "language": "python",
              "name": ""
            },
            {
              "code": "const axios = require('axios');\n\nconst url = 'https://api-sandbox.seamlesshr.app/biometric/process';\n\nconst payload = [{\n  attendanceId: \"2342\",\n  dateTime: \"2025-07-07T13:45:30\",\n  type: \"sm\",\n  deviceSN: \"344\"\n}];\n\nconst headers = {\n  'Content-Type': 'application/json',\n};\n\naxios.post(url, payload, { headers })\n  .then(response => {\n    console.log(`✅ HTTP ${response.status}`);\n    console.log('Response:', response.data);\n  })\n  .catch(error => {\n    if (error.response) {\n      console.error(`❌ HTTP ${error.response.status}`);\n      console.error('Response:', error.response.data);\n    } else {\n      console.error('❌ Error:', error.message);\n    }\n  });\n",
              "language": "node",
              "name": ""
            }
          ],
          "samples-languages": [
            "shell",
            "javascript",
            "php",
            "python",
            "node"
          ]
        },
        "summary": "Copy of "
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