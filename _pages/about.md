---
layout: about
title: About
permalink: /
subtitle: Project Assistant Professor, JSK Robotics Lab, The University of Tokyo

profile:
  align: right
  image: prof_pic.jpg
  image_circular: false # crops the image to make it circular
  # more_info: >

selected_papers: false # includes a list of papers marked as "selected={true}"
social: true # includes social icons at the bottom of the page

announcements:
  enabled: true # includes a list of news items
  scrollable: true # adds a vertical scroll bar if there are more than 3 news items
  limit: 5 # leave blank to include all the news in the `_news` folder

latest_posts:
  enabled: false
  scrollable: true # adds a vertical scroll bar if there are more than 3 new posts items
  limit: 3 # leave blank to include all the blog posts
_styles: |
  ol.bibliography {
    list-style: decimal;
    padding-left: 1.5rem;
    margin-top: 0.25rem;
  }

  ol.bibliography li {
    margin-bottom: 0.5rem;
    font-size: 0.93rem;
    line-height: 1.35;
  }

  ol.bibliography li .pub-title {
    font-weight: 400;
  }

  ol.bibliography li .self-author {
    font-weight: 700;
  }

  h2.bibliography {
    display: none;
  }
---

My research lies at the intersection of biological understanding and intelligent machine design, with a focus on biomimetic robotics to investigate biological systems and their underlying principles.

I take a constructive approach, building robotic systems grounded in physiological hierarchies, particularly starting from the tissue level, including receptor-level sensing, proprioception, fluid lubrication, and musculoskeletal mechanisms.

## Research Keywords

My research explores explores principles of living systems through biomimetic robots.

- Robotics
- Biomimetics
- Neuroscience
- Physiology
- Embodied Intelligence
- Constructive Understanding

## Publications

Selected publications below highlight two directions in my research: one from the perspective of constructive understanding, and one from the perspective of biomimetics and soft robotics.

{% bibliography --template bib-compact --group_by none --query @*[selected=true] %}

The full publication list is available on the [Works & Publications page](/publications/).
