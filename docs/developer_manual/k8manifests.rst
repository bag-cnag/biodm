Kubernetes manifests
====================

``BioDM`` features a way to integrate on demand launching of Kubernetes ``manifests``.

A ``K8sManifest`` is tied to a table, and a ``k8sService`` whose mission is simply to call
 ``K8sManifest.gen_manifest`` method in a `postfix` way, passing a new table object and the current
 session and submit that manifest to the cluster.

To implement a new type of instance on demand, this method shall return a valid manifest as a
python dictionary. Moreover a ``K8sManifest`` may indicate a specific namespace into which it shall
be submitted.

This class acts as an extra layer in the regular pipeline. Or depending how you see it, replaces
the Controller as manifests are not really expected to expose routes on their own.

You may refer to visualization feature in ``example`` project, that leverages such manifest
in order to implement an extra route at ``/files/{id}/visualize``. 


K8sController
-------------

In a future version of ``BioDM`` it is expected that this controller implements a set of joined
administration features for all manifests and their running instances.
