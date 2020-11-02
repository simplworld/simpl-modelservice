{
    "version": 2,
    "controller": {},
    "workers": [
        {
            "type": "router",
            "realms": [
                {
                    "name": "{{ realm }}",
                    "roles": [
                        {% if not MONITORING_ENABLED %}
                        {
                            "name": "anonymous",
                            "permissions": [
                                {
                                    "uri": "*",
                                    "allow": {
                                        "register": false,
                                        "call": false,
                                        "publish": false,
                                        "subscribe": false
                                    }
                                }
                            ]
                        },
                        {% else %}
                        {
                            "name": "anonymous",
                            "permissions": [
                                {
                                    "uri": "*",
                                    "allow": {
                                        "call": true,
                                        "register": true,
                                        "publish": true,
                                        "subscribe": true
                                    },
                                    "disclose": {
                                        "caller": true,
                                        "publisher": true
                                    },
                                    "cache": true
                                }
                            ]
                        },
                        {% endif %}
                        {
                            "name": "model",
                            "permissions": [
                                {
                                    "uri": "*",
                                    "allow": {
                                        "call": true,
                                        "register": true,
                                        "publish": true,
                                        "subscribe": true
                                    },
                                    "disclose": {
                                        "caller": true,
                                        "publisher": true
                                    },
                                    "cache": true
                                }
                            ]
                        },
                        {% if PROFILING_ENABLED %}
                        {# FYI It's very possible this won't work correctly after auth/permissions fixes #}
                            "name": "profiler",
                            "permissions": [
                                {
                                    "uri": "*",
                                    "allow": {
                                        "call": true,
                                        "register": true,
                                        "publish": true,
                                        "subscribe": true
                                    },
                                    "disclose": {
                                        "caller": true,
                                        "publisher": true
                                    },
                                    "cache": true
                                }
                            ]
                        }, {% endif %}
                        {
                            "name": "browser",
                            "authorizer": "world.simpl.authorize"
                        }
                    ]
                }
            ],
            {% comment %}
            "components": [
                {
                   "type": "class",
                   "realm": "realm1",
                   "role": "authorizer",
                   "classname": "modelservice.authorization.SimplAuthorizationComponent"
                }
            ],
            {% endcomment %}
            "transports": [
                {
                    "type": "web",
                    "endpoint": {
                        "type": "tcp",
                        "port": {{ port }},
                        "backlog": 1000
                    },
                    "paths": {
                        "/": {
                            "type": "wsgi",
                            "module": "{{ wsgi_module }}",
                            "object": "{{ wsgi_object }}"
                        },
                        {% if MONITORING_ENABLED %}
                        "monitor": {
                            "type": "static",
                            "package": "modelservice",
                            "resource": "static/modelservice/monitor",
                            "options": {
                                "enable_directory_listing": true
                            }
                        },
                        {% endif %}
                        "ws": {
                            "type": "websocket",
                             "auth": {
                                "wampcra": {
                                    "type": "static",
                                    "users": {
                                        "model": {
                                            "secret": "{{ MODEL_TICKET }}",
                                            "role": "model"
                                        }
                                    }
                                },
                                "ticket": {
                                   "type": "dynamic",
                                   "authenticator": "world.simpl.authenticate"
                                },
                                "anonymous": {
                                    "type": "static",
                                    "role": "anonymous"
                                }
                            },
                            "options": {
                                "enable_webstatus": false,
                                "max_frame_size": 1048576,
                                "max_message_size": 67108864,
                                "auto_fragment_size": 65536,
                                "fail_by_drop": true,
                                "open_handshake_timeout": 2500,
                                "close_handshake_timeout": 1000,
                                "auto_ping_interval": 10000,
                                "auto_ping_timeout": 300000,
                                "auto_ping_size": 4
                            }
                        },
                        "callback": {
                            "type": "webhook",
                            "realm": "{{ realm }}",
                            "role": "service",
                            "options": {
                                "topic": "{{ ROOT_TOPIC }}.model.game.webhook_forward"
                            }
                        }{% if DEBUG %},
                        "publish": {
                            "type": "publisher",
                            "realm": "realm1",
                            "role": "service"
                        },
                        "call": {
                            "type": "caller",
                            "realm": "realm1",
                            "role": "service"
                        }
                        {% endif %}
                    }
                }
            ]
        },
        {
            "type": "guest",
            "executable": "manage.py",
            "arguments": ["run_guest"],
            "options": {
                "env": {
                    "vars": {
                        "HOSTNAME": "{{ hostname }}",
                        "PORT": "{{ port }}",
                        "MODEL_TICKET": "{{ MODEL_TICKET }}"
                    }
                }
            }
        }
    ]
}
